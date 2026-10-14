"""Single-process worker: drains the outbox, runs due jobs, ingests inbound
mail, and hands company replies to the agent runtime.

Restart-safe by construction: all state lives in the database; this loop can
be killed at any point and resumed without duplicate sends.
"""

import logging
import time
import uuid

from sqlalchemy.orm import Session

from karenbot.agent.runner import AgentRuntime
from karenbot.channels.base import ChannelAdapter
from karenbot.config import get_settings
from karenbot.db.session import get_session_factory
from karenbot.domain.enums import ACTIVE_STATES, Counterparty
from karenbot.domain.models import Case, Communication, ScheduledJob
from karenbot.workflows import inbound, outbox, scheduler

logger = logging.getLogger("karenbot.worker")


class Worker:
    def __init__(
        self,
        adapter: ChannelAdapter,
        runtime: AgentRuntime,
        worker_id: str | None = None,
        *,
        per_account: bool = False,
    ):
        """`per_account=True` resolves the adapter per outbox row / connected
        account (production, real providers). False uses the fixed adapter
        (dev/mock, tests)."""
        self.adapter = adapter
        self.runtime = runtime
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.per_account = per_account

    @property
    def session_factory(self):
        # Late-bound so the worker follows the current configuration (tests
        # and dev reconfiguration swap databases after construction).
        return get_session_factory()

    def _adapter_for_row(self, session: Session, row) -> ChannelAdapter:
        if not self.per_account:
            return self.adapter
        from karenbot.channels.resolver import resolve_outbox_adapter

        return resolve_outbox_adapter(session, row)

    def _inbound_adapters(self, session: Session) -> list[ChannelAdapter]:
        if not self.per_account:
            return [self.adapter]
        from karenbot.channels.resolver import inbound_adapters

        return inbound_adapters(session)

    # Each tick is one pass over: stuck recovery -> outbox -> jobs -> inbound.
    def tick(self) -> int:
        work_done = 0
        with self.session_factory() as session:
            for stuck in outbox.stuck_rows(session):
                try:
                    outbox.recover_row(session, stuck, self._adapter_for_row(session, stuck))
                    work_done += 1
                except Exception:
                    logger.exception("recovery failed for outbox row %s", stuck.id)
            session.commit()

        while True:
            with self.session_factory() as session:
                row = outbox.claim_next(session, self.worker_id)
                if row is None:
                    break
                try:
                    outbox.deliver(session, row, self._adapter_for_row(session, row))
                    work_done += 1
                except Exception:
                    logger.exception("outbox delivery failed for %s", row.id)

        while True:
            with self.session_factory() as session:
                job = scheduler.claim_due_job(session, self.worker_id)
                if job is None:
                    break
                try:
                    scheduler.run_job(session, job, self.job_handlers())
                    work_done += 1
                except Exception:
                    logger.exception("job failed: %s", job.id)

        with self.session_factory() as session:
            new_comms = []
            for source in self._inbound_adapters(session):
                new_comms.extend(inbound.poll_inbound(session, source))
            session.commit()
            for comm in new_comms:
                if comm.counterparty == Counterparty.COMPANY.value:
                    self._handle_reply(session, comm)
                    work_done += 1
            session.commit()
        return work_done

    def _handle_reply(self, session: Session, comm: Communication) -> None:
        case = session.get(Case, comm.case_id)
        if case is None:
            return
        # Paused (BLOCKED) or terminal cases: the reply is ingested and
        # recorded, but the agent must not act until an admin resumes.
        if case.status not in {s.value for s in ACTIVE_STATES}:
            logger.info("case %s is %s; reply recorded, agent skipped", case.id, case.status)
            return
        try:
            self.runtime.handle_company_reply(session, case, comm)
        except Exception:
            logger.exception("agent failed to handle reply %s", comm.id)
            session.rollback()

    def job_handlers(self) -> dict[str, scheduler.JobHandler]:
        return {"follow_up": self._run_follow_up_job}

    def _run_follow_up_job(self, session: Session, job: ScheduledJob) -> None:
        if job.case_id is None:
            return
        case = session.get(Case, job.case_id)
        if case is None:
            return
        # No reply since the last send? Nudge. (A reply would have moved the
        # case out of AWAITING_RESPONSE.)
        if case.status == "AWAITING_RESPONSE":
            self.runtime._send_follow_up(  # noqa: SLF001 - worker is a trusted orchestrator
                session,
                case,
                prompt_version="scheduler",
                note=(job.payload or {}).get("note") or "status_inquiry",
                counter_amount=None,
            )

    def run_forever(self) -> None:
        settings = get_settings()
        logger.info("worker %s started", self.worker_id)
        while True:
            try:
                did = self.tick()
            except Exception:
                logger.exception("worker tick failed")
                did = 0
            if did == 0:
                time.sleep(settings.worker_poll_seconds)


def main() -> None:
    from karenbot.observability import init_observability

    init_observability("worker")
    from karenbot.channels.mock_email import MockEmailAdapter
    from karenbot.channels.registry import get_email_adapter
    from karenbot.llm.scripted import ScriptedClient
    from karenbot.simulator.personas import PERSONAS

    settings = get_settings()
    llm = ScriptedClient()
    if settings.llm_provider == "anthropic":
        from karenbot.llm.anthropic_client import AnthropicClient

        llm = AnthropicClient()  # type: ignore[assignment]
    if settings.email_provider == "mock":
        adapter = get_email_adapter("mock")
        if isinstance(adapter, MockEmailAdapter) and adapter.responder is None:
            adapter.responder = PERSONAS["lowball_then_accept"]
        Worker(adapter, AgentRuntime(llm)).run_forever()
    else:
        # Real providers: resolve the adapter per connected account.
        Worker(MockEmailAdapter(), AgentRuntime(llm), per_account=True).run_forever()


if __name__ == "__main__":
    main()
