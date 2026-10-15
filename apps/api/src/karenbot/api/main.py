"""KarenBot API (MVP).

Auth is a dev stub (X-User-Email header) until Clerk JWT verification lands.
The /dev router (enabled by KARENBOT_DEV_MODE) seeds demo data and drives the
in-process mock-email worker so the full case lifecycle can be exercised from
the browser with no external services.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot import services
from karenbot.agent.runner import AgentRuntime
from karenbot.channels.mock_email import MockEmailAdapter
from karenbot.config import get_settings
from karenbot.db.session import get_session_factory
from karenbot.domain.enums import ExecutionStatus
from karenbot.domain.models import (
    AgentAction,
    AuditEvent,
    Case,
    Communication,
    Company,
    User,
)
from karenbot.llm.scripted import ScriptedClient
from karenbot.observability import init_observability  # noqa: E402
from karenbot.simulator.personas import PERSONAS
from karenbot.workflows.worker import Worker

init_observability("api")
app = FastAPI(title="KarenBot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def current_user(
    x_user_email: str = Header(..., description="Dev auth stub"),
    db: Session = Depends(get_db),
) -> User:
    user = db.scalars(select(User).where(User.email == x_user_email)).first()
    if user is None:
        raise HTTPException(401, "unknown user — call POST /dev/seed first")
    return user


def _llm():
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        from karenbot.llm.anthropic_client import AnthropicClient

        return AnthropicClient()
    return ScriptedClient()


# In-process mock channel + worker for dev/demo. Module-level so provider
# thread state and idempotency receipts survive across requests.
_adapter = MockEmailAdapter(responder=PERSONAS["lowball_then_accept"])
_runtime = AgentRuntime(_llm())
_worker = Worker(_adapter, _runtime, worker_id="api-dev-worker")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# --------------------------------------------------------------------------
# Companies
# --------------------------------------------------------------------------


class CompanyOut(BaseModel):
    id: uuid.UUID
    name: str
    industry: str
    size_class: str
    targetable: bool
    refuses_third_party: bool


@app.get("/companies", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db)) -> list[CompanyOut]:
    return [
        CompanyOut(
            id=c.id,
            name=c.name,
            industry=c.industry,
            size_class=c.size_class,
            targetable=services.company_is_targetable(c),
            refuses_third_party=c.refuses_third_party,
        )
        for c in db.scalars(select(Company).order_by(Company.name))
    ]


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------


class CaseCreate(BaseModel):
    company_name: str
    category: str
    description: str
    requested_amount: Decimal | None = None
    incident_date: datetime | None = None


class CaseOut(BaseModel):
    id: uuid.UUID
    status: str
    category: str
    description: str
    requested_amount: Decimal | None
    currency: str
    company_name: str | None = None
    eligibility_basis: str | None = None
    facts: dict[str, Any] = {}

    model_config = {"from_attributes": True}


class CaseCreated(BaseModel):
    case: CaseOut
    karen_questions: list[str]


def _case_out(db: Session, case: Case) -> CaseOut:
    company = db.get(Company, case.company_id)
    out = CaseOut.model_validate(case)
    out.company_name = company.name if company else None
    return out


def _owned_case(db: Session, case_id: uuid.UUID, user: User) -> Case:
    case = db.get(Case, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(404, "case not found")
    return case


@app.post("/cases", response_model=CaseCreated)
def create_case(
    payload: CaseCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CaseCreated:
    company = db.scalars(select(Company).where(Company.name == payload.company_name)).first()
    if company is None:
        raise HTTPException(404, "company not supported yet")
    if not services.company_is_targetable(company):
        raise HTTPException(
            422,
            "KarenBot only takes on large companies — this business is not "
            "one we'll go after.",
        )
    case = services.create_case(
        db,
        user=user,
        company=company,
        category=payload.category,
        description=payload.description,
        requested_amount=payload.requested_amount,
        incident_date=payload.incident_date,
    )
    intake = _runtime.run_intake(db, case)
    return CaseCreated(case=_case_out(db, case), karen_questions=intake.missing_info)


@app.get("/cases", response_model=list[CaseOut])
def list_cases(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[CaseOut]:
    cases = db.scalars(
        select(Case).where(Case.user_id == user.id).order_by(Case.created_at.desc())
    ).all()
    return [_case_out(db, c) for c in cases]


@app.get("/cases/{case_id}", response_model=CaseOut)
def get_case(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CaseOut:
    return _case_out(db, _owned_case(db, case_id, user))


class EvidenceIn(BaseModel):
    evidence_type: str
    summary: str


@app.post("/cases/{case_id}/evidence", response_model=CaseOut)
def add_evidence(
    case_id: uuid.UUID,
    payload: EvidenceIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CaseOut:
    case = _owned_case(db, case_id, user)
    services.add_evidence(
        db, case, evidence_type=payload.evidence_type, summary=payload.summary
    )
    return _case_out(db, case)


class EligibilityOut(BaseModel):
    eligible: bool
    basis: str | None
    reasons: list[str]
    status: str


@app.post("/cases/{case_id}/intake/complete", response_model=EligibilityOut)
def complete_intake(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EligibilityOut:
    case = _owned_case(db, case_id, user)
    if case.status == "AWAITING_INFORMATION":
        _runtime.complete_intake(db, case)
    result = _runtime.assess_eligibility(db, case)
    return EligibilityOut(
        eligible=result.eligible, basis=result.basis, reasons=result.reasons, status=case.status
    )


class AuthorizeIn(BaseModel):
    signed_name: str


class AuthorizeOut(BaseModel):
    status: str
    loa_text: str


@app.post("/cases/{case_id}/authorize", response_model=AuthorizeOut)
def authorize(
    case_id: uuid.UUID,
    payload: AuthorizeIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AuthorizeOut:
    case = _owned_case(db, case_id, user)
    auth = services.grant_full_authorization(
        db,
        case,
        signed_name=payload.signed_name,
        signature_ip=request.client.host if request.client else None,
        signature_user_agent=request.headers.get("user-agent"),
    )
    return AuthorizeOut(status=case.status, loa_text=auth.loa_text or "")


class ContactOut(BaseModel):
    decision: str
    reasons: list[str]
    status: str


@app.post("/cases/{case_id}/contact", response_model=ContactOut)
def initiate_contact(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ContactOut:
    case = _owned_case(db, case_id, user)
    decision = _runtime.initiate_contact(db, case)
    return ContactOut(
        decision=decision.decision.value, reasons=decision.reasons, status=case.status
    )


class CommunicationOut(BaseModel):
    id: uuid.UUID
    channel: str
    direction: str
    counterparty: str
    subject: str | None
    body: str
    sent_at: datetime | None
    received_at: datetime | None
    created_at: datetime
    classification: dict[str, Any] = {}

    model_config = {"from_attributes": True}


@app.get("/cases/{case_id}/communications", response_model=list[CommunicationOut])
def list_communications(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[Communication]:
    _owned_case(db, case_id, user)
    return list(
        db.scalars(
            select(Communication)
            .where(Communication.case_id == case_id)
            .order_by(Communication.created_at)
        )
    )


class AuditOut(BaseModel):
    actor_type: str
    event_type: str
    event_payload: dict[str, Any]
    timestamp: datetime

    model_config = {"from_attributes": True}


@app.get("/cases/{case_id}/audit", response_model=list[AuditOut])
def list_audit(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[AuditEvent]:
    _owned_case(db, case_id, user)
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.case_id == case_id)
            .order_by(AuditEvent.timestamp)
        )
    )


class ApprovalOut(BaseModel):
    id: uuid.UUID
    action_type: str
    proposed_action: dict[str, Any]
    policy_reasons: list[str]

    model_config = {"from_attributes": True}


@app.get("/cases/{case_id}/approvals", response_model=list[ApprovalOut])
def list_approvals(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[AgentAction]:
    case = _owned_case(db, case_id, user)
    return services.pending_approvals(db, case)


@app.post("/approvals/{action_id}/approve")
def approve(
    action_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(AgentAction, action_id)
    if row is None:
        raise HTTPException(404, "action not found")
    case = _owned_case(db, row.case_id, user)
    if row.execution_status != ExecutionStatus.AWAITING_APPROVAL.value:
        raise HTTPException(409, "action is not awaiting approval")
    services.approve_action(db, row)
    return {"status": case.status}


@app.post("/cases/{case_id}/confirm-recovery")
def confirm_recovery(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    case = _owned_case(db, case_id, user)
    try:
        services.confirm_recovery_received(db, case)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": case.status}


@app.post("/cases/{case_id}/revoke")
def revoke(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    case = _owned_case(db, case_id, user)
    services.revoke_authorization(db, case)
    return {"status": case.status}


# --------------------------------------------------------------------------
# Dev simulator (local development only)
# --------------------------------------------------------------------------

from karenbot.api import admin, banking, connect  # noqa: E402

app.include_router(connect.build_router(), prefix="/connect", tags=["connect"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(banking.build_router(lambda: _runtime), prefix="/banking", tags=["banking"])

if get_settings().dev_mode:
    from karenbot.api import dev

    # Getters so tests/dev tooling can swap the live instances.
    app.include_router(
        dev.build_router(lambda: _adapter, lambda: _worker), prefix="/dev", tags=["dev"]
    )
