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
from karenbot.domain.enums import Counterparty
from karenbot.domain.models import Case, Communication, ScheduledJob
from karenbot.workflows import inbound, outbox, scheduler

logger = logging.getLogger("karenbot.worker")


class Worker:
    def __init__(self, adapter: ChannelAdapter, runtime: AgentRuntime, worker_id: str | None = None):
        self.adapter = adapter
        self.runtime = runtime
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.session_factory = get_session_factory()

    # Each tick is one pass over: stuck recovery -> outbox -> jobs -> inbound.
    def tick(self) -> int:
        work_done = 0
        with self.session_factory() as session:
            work_done += outbox.recover_stuck(session, self.adapter)

        while True:
            with self.session_factory() as session:
                row = outbox.claim_next(session, self.worker_id)
                if row is None:
                    break
                try:
                    outbox.deliver(session, row, self.adapter)
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
            new_comms = inbound.poll_inbound(session, self.adapter)
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
    logging.basicConfig(level=logging.INFO)
    from karenbot.channels.mock_email import MockEmailAdapter
    from karenbot.llm.scripted import ScriptedClient
    from karenbot.simulator.personas import PERSONAS

    settings = get_settings()
    llm = ScriptedClient()
    if settings.llm_provider == "anthropic":
        from karenbot.llm.anthropic_client import AnthropicClient

        llm = AnthropicClient()  # type: ignore[assignment]
    adapter = MockEmailAdapter(responder=PERSONAS["lowball_then_accept"])
    Worker(adapter, AgentRuntime(llm)).run_forever()


if __name__ == "__main__":
    main()
