"""Recurring-bill discovery: link accounts, surface subscriptions, act.

The moral code shapes the action path:
- Enterprise merchants -> a normal agent case (KarenBot contacts them).
- Everyone else (unclassified/small merchants) -> an ASSIST case: KarenBot
  drafts the cancellation/negotiation letter; the customer sends it. We
  never auto-classify a merchant as targetable.
"""

import re
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot import services
from karenbot.discovery.plaid import PlaidClient
from karenbot.domain.enums import ActorType
from karenbot.domain.models import (
    AuditEvent,
    BankConnection,
    Case,
    Company,
    RecurringCharge,
    User,
    utcnow,
)
from karenbot.security.crypto import decrypt_json, encrypt_json

CANCEL = "subscription_cancellation"
NEGOTIATE = "bill_negotiation"
REFUND = "recurring_charge_refund"

ACTION_CATEGORIES = {"cancel": CANCEL, "negotiate": NEGOTIATE, "refund": REFUND}


def normalize_merchant(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9 ]", "", name.lower())
    cleaned = re.sub(
        r"\b(inc|llc|ltd|corp|co|the|subscription|membership|rewards?)\b", "", cleaned
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def connect_bank(
    session: Session, user: User, public_token: str, client: PlaidClient
) -> BankConnection:
    linked = client.exchange_public_token(public_token)
    connection = session.scalars(
        select(BankConnection).where(
            BankConnection.user_id == user.id,
            BankConnection.provider == "plaid",
            BankConnection.item_id == linked.item_id,
        )
    ).first()
    if connection is None:
        connection = BankConnection(
            user_id=user.id, provider="plaid", item_id=linked.item_id
        )
        session.add(connection)
    connection.institution_name = linked.institution_name
    connection.encrypted_access_token = encrypt_json({"access_token": linked.access_token})
    connection.status = "active"
    connection.revoked_at = None
    session.add(
        AuditEvent(
            actor_type=ActorType.CUSTOMER.value,
            actor_id=str(user.id),
            event_type="bank.connected",
            event_payload={"institution": linked.institution_name},
        )
    )
    session.flush()
    return connection


def revoke_bank(session: Session, connection: BankConnection) -> None:
    connection.status = "revoked"
    connection.revoked_at = utcnow()
    connection.encrypted_access_token = None  # drop credentials immediately
    session.flush()


def refresh_recurring(
    session: Session, user: User, client: PlaidClient
) -> list[RecurringCharge]:
    """Pull recurring streams for every active connection and upsert charges."""
    connections = session.scalars(
        select(BankConnection).where(
            BankConnection.user_id == user.id,
            BankConnection.status == "active",
        )
    ).all()
    charges: list[RecurringCharge] = []
    for connection in connections:
        if not connection.encrypted_access_token:
            continue
        token = decrypt_json(connection.encrypted_access_token)["access_token"]
        for stream in client.get_recurring(token):
            normalized = normalize_merchant(stream.merchant_name)
            charge = session.scalars(
                select(RecurringCharge).where(
                    RecurringCharge.user_id == user.id,
                    RecurringCharge.normalized_merchant == normalized,
                    RecurringCharge.cadence == stream.cadence,
                )
            ).first()
            if charge is None:
                charge = RecurringCharge(
                    user_id=user.id,
                    bank_connection_id=connection.id,
                    merchant_name=stream.merchant_name,
                    normalized_merchant=normalized,
                    amount=stream.amount,
                    currency=stream.currency,
                    cadence=stream.cadence,
                )
                session.add(charge)
            charge.amount = stream.amount
            charge.first_seen = stream.first_date
            charge.last_seen = stream.last_date
            charge.occurrences = stream.occurrences
            charge.company_id = _match_company(session, stream.merchant_name)
            charges.append(charge)
    session.flush()
    return charges


def _match_company(session: Session, merchant_name: str) -> uuid.UUID | None:
    normalized = normalize_merchant(merchant_name)
    for company in session.scalars(select(Company)).all():
        if normalize_merchant(company.name) and normalize_merchant(company.name) in normalized:
            return company.id
    return None


def yearly_cost(charge: RecurringCharge) -> Decimal:
    multiplier = {"weekly": 52, "monthly": 12, "yearly": 1}.get(charge.cadence, 12)
    return charge.amount * multiplier


def create_case_from_charge(
    session: Session, user: User, charge: RecurringCharge, action: str
) -> Case:
    if action not in ACTION_CATEGORIES:
        raise ValueError(f"unknown action '{action}'")
    if charge.status == "case_created" and charge.case_id is not None:
        existing = session.get(Case, charge.case_id)
        if existing is not None:
            return existing

    company = session.get(Company, charge.company_id) if charge.company_id else None
    if company is None:
        # Unknown merchant: create an unclassified (never-targetable) record.
        company = session.scalars(
            select(Company).where(Company.name == charge.merchant_name)
        ).first()
        if company is None:
            company = Company(
                name=charge.merchant_name, industry="subscription", size_class="unclassified"
            )
            session.add(company)
            session.flush()

    category = ACTION_CATEGORIES[action]
    verb = {
        "cancel": "cancel this subscription",
        "negotiate": "negotiate this bill down",
        "refund": "request a refund of recent charges",
    }[action]
    description = (
        f"Recurring {charge.cadence} charge of {charge.currency} {charge.amount} from "
        f"{charge.merchant_name} ({charge.occurrences} charges on record, roughly "
        f"{charge.currency} {yearly_cost(charge):.2f}/year). The customer wants to {verb}."
    )
    requested = charge.amount if action == "refund" else None

    case = services.create_case(
        session,
        user=user,
        company=company,
        category=category,
        description=description,
        requested_amount=requested,
        assist_mode_ok=True,
    )
    services.add_evidence(
        session,
        case,
        evidence_type="bank_transaction_history",
        summary=(
            f"{charge.occurrences} {charge.cadence} charges of {charge.currency} "
            f"{charge.amount} from '{charge.merchant_name}' on the customer's linked "
            f"account (last seen {charge.last_seen:%Y-%m-%d})"
            if charge.last_seen
            else f"{charge.occurrences} {charge.cadence} charges of {charge.currency} "
            f"{charge.amount} from '{charge.merchant_name}'"
        ),
    )
    charge.status = "case_created"
    charge.case_id = case.id
    session.add(
        AuditEvent(
            actor_type=ActorType.CUSTOMER.value,
            actor_id=str(user.id),
            case_id=case.id,
            event_type="subscription.action_started",
            event_payload={
                "merchant": charge.merchant_name,
                "action": action,
                "contact_mode": case.contact_mode,
            },
        )
    )
    session.flush()
    return case


def dismiss_charge(session: Session, charge: RecurringCharge) -> None:
    charge.status = "dismissed"
    session.flush()
