"""Durable timers: claim and run due scheduled jobs."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import CursorResult, select, update
from sqlalchemy.orm import Session

from karenbot.domain.enums import JobStatus
from karenbot.domain.models import ScheduledJob

JobHandler = Callable[[Session, ScheduledJob], None]

MAX_ATTEMPTS = 3


def claim_due_job(
    session: Session, worker_id: str, lease_seconds: int = 300
) -> ScheduledJob | None:
    now = datetime.now(UTC)
    job_id = session.scalars(
        select(ScheduledJob.id)
        .where(ScheduledJob.status == JobStatus.PENDING.value, ScheduledJob.run_at <= now)
        .order_by(ScheduledJob.run_at)
        .limit(1)
    ).first()
    if job_id is None:
        return None
    claimed: CursorResult[Any] = session.execute(  # type: ignore[assignment]
        update(ScheduledJob)
        .where(ScheduledJob.id == job_id, ScheduledJob.status == JobStatus.PENDING.value)
        .values(
            status=JobStatus.RUNNING.value,
            locked_by=worker_id,
            locked_until=now + timedelta(seconds=lease_seconds),
            attempts=ScheduledJob.attempts + 1,
        )
    )
    session.commit()
    if claimed.rowcount != 1:
        return None
    return session.get(ScheduledJob, job_id)


def run_job(session: Session, job: ScheduledJob, handlers: dict[str, JobHandler]) -> None:
    handler = handlers.get(job.job_type)
    try:
        if handler is None:
            raise RuntimeError(f"no handler for job type {job.job_type}")
        handler(session, job)
        job.status = JobStatus.DONE.value
        session.commit()
    except Exception:
        session.rollback()
        job = session.merge(job)
        job.status = (
            JobStatus.FAILED.value if job.attempts >= MAX_ATTEMPTS else JobStatus.PENDING.value
        )
        session.commit()
        raise
