"""Banking + subscriptions API: link accounts (Plaid), surface recurring
charges, and turn them into cases (cancel / negotiate / refund).

After an action the case lands in AWAITING_AUTHORIZATION — the customer
still signs the LOA and (for agent cases) fires contact from the case page;
discovery never skips the authorization step.
"""

import uuid
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.agent.runner import AgentRuntime
from karenbot.discovery import service as discovery
from karenbot.discovery.plaid import get_plaid_client
from karenbot.domain.enums import ActorType, CaseEvent
from karenbot.domain.models import AuditEvent, BankConnection, RecurringCharge, User
from karenbot.domain.state_machine import transition


class BankConnectionOut(BaseModel):
    id: uuid.UUID
    provider: str
    institution_name: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    source: str  # plaid | email_scan
    merchant_name: str
    amount: Decimal
    currency: str
    cadence: str
    occurrences: int
    last_seen: datetime | None
    yearly_cost: Decimal
    status: str
    case_id: uuid.UUID | None
    company_targetable: bool


class ExchangeIn(BaseModel):
    public_token: str
    institution_name: str | None = None


class ActionIn(BaseModel):
    action: Literal["cancel", "negotiate", "refund", "dismiss"]


def build_router(get_runtime: Callable[[], AgentRuntime]) -> APIRouter:
    from karenbot.api.main import current_user, get_db

    router = APIRouter()

    @router.post("/link-token")
    def link_token(user: User = Depends(current_user)) -> dict:
        try:
            return {"link_token": get_plaid_client().create_link_token(str(user.id))}
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

    @router.post("/exchange", response_model=BankConnectionOut)
    def exchange(
        payload: ExchangeIn,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> BankConnection:
        connection = discovery.connect_bank(db, user, payload.public_token, get_plaid_client())
        if payload.institution_name and not connection.institution_name:
            connection.institution_name = payload.institution_name
        # First sync immediately so the user sees results on return.
        discovery.refresh_recurring(db, user, get_plaid_client())
        return connection

    @router.get("/connections", response_model=list[BankConnectionOut])
    def connections(
        user: User = Depends(current_user), db: Session = Depends(get_db)
    ) -> list[BankConnection]:
        return list(
            db.scalars(
                select(BankConnection)
                .where(BankConnection.user_id == user.id)
                .order_by(BankConnection.created_at.desc())
            )
        )

    @router.post("/connections/{connection_id}/revoke")
    def revoke(
        connection_id: uuid.UUID,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> dict:
        connection = db.get(BankConnection, connection_id)
        if connection is None or connection.user_id != user.id:
            raise HTTPException(404, "connection not found")
        discovery.revoke_bank(db, connection)
        return {"status": "revoked"}

    @router.post("/refresh", response_model=list[SubscriptionOut])
    def refresh(
        user: User = Depends(current_user), db: Session = Depends(get_db)
    ) -> list[SubscriptionOut]:
        discovery.refresh_recurring(db, user, get_plaid_client())
        return _list(db, user)

    @router.post("/subscriptions/scan-email", response_model=list[SubscriptionOut])
    def scan_email_subscriptions(
        user: User = Depends(current_user), db: Session = Depends(get_db)
    ) -> list[SubscriptionOut]:
        """User-initiated: detect recurring charges from billing receipts in
        the connected mailbox. No bank connection required."""
        from karenbot.channels.oauth import ReconnectRequired
        from karenbot.discovery.inbox_scan import get_inbox_scanner

        try:
            scanner = get_inbox_scanner(db, user)
        except NotImplementedError as exc:
            raise HTTPException(503, str(exc)) from exc
        try:
            found = discovery.refresh_email_recurring(db, user, scanner)
        except ReconnectRequired as exc:
            raise HTTPException(409, str(exc)) from exc
        db.add(
            AuditEvent(
                actor_type=ActorType.CUSTOMER.value,
                actor_id=str(user.id),
                event_type="scan.email_subscriptions",
                event_payload={"found": len(found)},
            )
        )
        return _list(db, user)

    @router.get("/subscriptions", response_model=list[SubscriptionOut])
    def subscriptions(
        user: User = Depends(current_user), db: Session = Depends(get_db)
    ) -> list[SubscriptionOut]:
        return _list(db, user)

    def _list(db: Session, user: User) -> list[SubscriptionOut]:
        from karenbot import services as core_services
        from karenbot.domain.models import Company

        out = []
        charges = db.scalars(
            select(RecurringCharge)
            .where(RecurringCharge.user_id == user.id)
            .order_by(RecurringCharge.amount.desc())
        ).all()
        for charge in charges:
            company = db.get(Company, charge.company_id) if charge.company_id else None
            out.append(
                SubscriptionOut(
                    id=charge.id,
                    source=charge.source,
                    merchant_name=charge.merchant_name,
                    amount=charge.amount,
                    currency=charge.currency,
                    cadence=charge.cadence,
                    occurrences=charge.occurrences,
                    last_seen=charge.last_seen,
                    yearly_cost=discovery.yearly_cost(charge),
                    status=charge.status,
                    case_id=charge.case_id,
                    company_targetable=bool(
                        company and core_services.company_is_targetable(company)
                    ),
                )
            )
        return out

    @router.post("/subscriptions/{charge_id}/action")
    def act(
        charge_id: uuid.UUID,
        payload: ActionIn,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> dict:
        charge = db.get(RecurringCharge, charge_id)
        if charge is None or charge.user_id != user.id:
            raise HTTPException(404, "subscription not found")
        if payload.action == "dismiss":
            discovery.dismiss_charge(db, charge)
            return {"status": "dismissed"}

        case = discovery.create_case_from_charge(db, user, charge, payload.action)
        # Discovery cases carry their own evidence; move straight to the
        # authorization step (the customer must still sign the LOA).
        if case.status == "DISCOVERED":
            transition(db, case, CaseEvent.INTAKE_COMPLETE, actor_type=ActorType.AGENT)
            get_runtime().assess_eligibility(db, case)
        return {
            "status": case.status,
            "case_id": str(case.id),
            "contact_mode": case.contact_mode,
        }

    return router
