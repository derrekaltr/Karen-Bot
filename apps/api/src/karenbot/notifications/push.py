"""Push delivery: transactional enqueue, worker-side send, dead-token cleanup.

Flow:
1. `transition()` calls `enqueue_for_transition` inside the caller's DB
   transaction. If the case has notifiable news and the user has a phone,
   a `push_notification` ScheduledJob is written — so a push exists if and
   only if the status change commits, and nothing slow (HTTP) happens on
   the request path. The job's idempotency key is the transition's audit
   event id: one push per transition, ever.
2. The worker runs the job: resolve the user's active devices at send time,
   send one batch to Expo's push service, disable tokens Expo rejects as
   DeviceNotRegistered, and schedule a receipts check.
3. ~15 minutes later `push_receipts` asks Expo how APNs/FCM delivery went
   and disables tokens that turned out to be dead.

Failures raise so the scheduler retries (MAX_ATTEMPTS); a lost push is
acceptable, a duplicate is merely annoying — case state never depends on it.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.config import get_settings
from karenbot.domain.enums import ActorType, CaseEvent, CaseStatus
from karenbot.domain.models import AuditEvent, Case, PushDevice, ScheduledJob, utcnow
from karenbot.notifications.content import content_for_transition

logger = logging.getLogger(__name__)

JOB_PUSH = "push_notification"
JOB_RECEIPTS = "push_receipts"

EXPO_SEND_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
EXPO_BATCH_LIMIT = 100
# Expo recommends checking receipts ~15 minutes after sending.
RECEIPT_DELAY = timedelta(minutes=15)
DEAD_TOKEN_ERRORS = frozenset({"DeviceNotRegistered"})


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


class PushClient(Protocol):
    def send(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Send messages; return one Expo ticket per message, in order."""
        ...

    def receipts(self, ids: list[str]) -> dict[str, dict[str, Any]]:
        """Receipt per ticket id (ids without a receipt yet are omitted)."""
        ...


class ExpoPushClient:
    def __init__(self, access_token: str = "", timeout: float = 15.0):
        self._headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/json",
        }
        if access_token:
            self._headers["Authorization"] = f"Bearer {access_token}"
        self._timeout = timeout

    def _post(self, url: str, payload: Any) -> dict[str, Any]:
        response = httpx.post(url, json=payload, headers=self._headers, timeout=self._timeout)
        response.raise_for_status()  # 429/5xx -> exception -> scheduler retry
        body = response.json()
        if body.get("errors") and "data" not in body:
            raise RuntimeError(f"expo push request rejected: {body['errors']}")
        return body

    def send(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tickets: list[dict[str, Any]] = []
        for start in range(0, len(messages), EXPO_BATCH_LIMIT):
            batch = messages[start : start + EXPO_BATCH_LIMIT]
            tickets.extend(self._post(EXPO_SEND_URL, batch)["data"])
        return tickets

    def receipts(self, ids: list[str]) -> dict[str, dict[str, Any]]:
        return self._post(EXPO_RECEIPTS_URL, {"ids": ids}).get("data", {})


class LogPushClient:
    """Dev/test stand-in: records what would have been sent."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for message in messages:
            logger.info("push (not sent): %s — %s", message.get("title"), message.get("body"))
        self.sent.extend(messages)
        return [{"status": "ok", "id": f"log-{uuid.uuid4()}"} for _ in messages]

    def receipts(self, ids: list[str]) -> dict[str, dict[str, Any]]:
        return {i: {"status": "ok"} for i in ids}


def get_push_client() -> PushClient:
    settings = get_settings()
    if settings.push_provider == "expo":
        return ExpoPushClient(access_token=settings.expo_access_token)
    return LogPushClient()


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------


def active_devices(session: Session, user_id: uuid.UUID) -> list[PushDevice]:
    return list(
        session.scalars(
            select(PushDevice).where(
                PushDevice.user_id == user_id, PushDevice.disabled_at.is_(None)
            )
        )
    )


def disable_token(session: Session, token: str, reason: str) -> None:
    device = session.scalars(select(PushDevice).where(PushDevice.token == token)).first()
    if device is not None and device.disabled_at is None:
        device.disabled_at = utcnow()
        device.disabled_reason = reason


# ---------------------------------------------------------------------------
# Enqueue (request path — no I/O)
# ---------------------------------------------------------------------------


def enqueue_for_transition(
    session: Session,
    case: Case,
    event: CaseEvent,
    *,
    actor_type: ActorType,
    to_status: CaseStatus,
    audit_event: AuditEvent,
) -> ScheduledJob | None:
    content = content_for_transition(
        session, case, event, actor_type=actor_type, to_status=to_status
    )
    if content is None or not active_devices(session, case.user_id):
        return None
    job = ScheduledJob(
        case_id=case.id,
        job_type=JOB_PUSH,
        run_at=datetime.now(UTC),
        idempotency_key=f"push:{audit_event.id}",
        payload={
            "user_id": str(case.user_id),
            "title": content.title,
            "body": content.body,
            "priority": content.priority,
            "data": content.data,
        },
    )
    session.add(job)
    return job


# ---------------------------------------------------------------------------
# Worker jobs
# ---------------------------------------------------------------------------


def run_push_job(session: Session, job: ScheduledJob, client: PushClient) -> None:
    payload = job.payload or {}
    devices = active_devices(session, uuid.UUID(payload["user_id"]))
    if not devices:
        return  # every phone signed out / went dead since enqueue
    messages = [
        {
            "to": device.token,
            "title": payload["title"],
            "body": payload["body"],
            "data": payload.get("data", {}),
            "priority": payload.get("priority", "default"),
            "sound": "default",
        }
        for device in devices
    ]
    tickets = client.send(messages)

    receipt_ids: dict[str, str] = {}
    for message, ticket in zip(messages, tickets, strict=False):
        if ticket.get("status") == "ok" and ticket.get("id"):
            receipt_ids[ticket["id"]] = message["to"]
            continue
        error = (ticket.get("details") or {}).get("error")
        if error in DEAD_TOKEN_ERRORS:
            disable_token(session, message["to"], error)
        else:
            logger.warning("push ticket error for job %s: %s", job.id, ticket)

    if receipt_ids:
        session.add(
            ScheduledJob(
                case_id=job.case_id,
                job_type=JOB_RECEIPTS,
                run_at=datetime.now(UTC) + RECEIPT_DELAY,
                idempotency_key=f"push-receipts:{job.id}",
                payload={"receipts": receipt_ids},
            )
        )


def run_receipts_job(session: Session, job: ScheduledJob, client: PushClient) -> None:
    by_id: dict[str, str] = (job.payload or {}).get("receipts", {})
    if not by_id:
        return
    receipts = client.receipts(list(by_id))
    for receipt_id, receipt in receipts.items():
        if receipt.get("status") == "ok":
            continue
        error = (receipt.get("details") or {}).get("error")
        token = by_id.get(receipt_id)
        if error in DEAD_TOKEN_ERRORS and token:
            disable_token(session, token, error)
        else:
            logger.warning("push receipt error %s: %s", receipt_id, receipt)
