"""System controls: DB-backed operational switches.

The kill switch is the emergency stop: when active, the policy engine denies
every action on every case. It is read fresh on each policy evaluation (no
caching) so flipping it takes effect on the next proposed action.
"""

from typing import Any

from sqlalchemy.orm import Session

from karenbot.domain.enums import ActorType
from karenbot.domain.models import AuditEvent, SystemControl

KILL_SWITCH = "kill_switch"


def get_control(session: Session, key: str) -> dict[str, Any]:
    row = session.get(SystemControl, key)
    return row.value if row else {}


def set_control(
    session: Session, key: str, value: dict[str, Any], *, admin_id: str
) -> None:
    row = session.get(SystemControl, key)
    if row is None:
        row = SystemControl(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    session.add(
        AuditEvent(
            actor_type=ActorType.ADMIN.value,
            actor_id=admin_id,
            event_type=f"control.{key}_changed",
            event_payload=value,
        )
    )
    session.flush()


def kill_switch_active(session: Session) -> bool:
    return bool(get_control(session, KILL_SWITCH).get("active", False))


def set_kill_switch(session: Session, active: bool, *, admin_id: str) -> None:
    set_control(session, KILL_SWITCH, {"active": active}, admin_id=admin_id)
