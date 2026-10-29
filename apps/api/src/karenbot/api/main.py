"""KarenBot API (MVP).

Auth is a dev stub (X-User-Email header) until Clerk JWT verification lands.
The /dev router (enabled by KARENBOT_DEV_MODE) seeds demo data and drives the
in-process mock-email worker so the full case lifecycle can be exercised from
the browser with no external services.
"""

import logging
import uuid
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Dev fallback port — used when another local app holds 3000.
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return JSON 500s through the middleware stack so CORS headers are
    present — otherwise browsers surface errors as an opaque
    'Failed to fetch' instead of a readable message."""
    logging.getLogger("karenbot.api").exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


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


# Clerk session JWT auth, with the X-User-Email fallback in dev mode only.
from karenbot.api.auth import current_user_factory  # noqa: E402

current_user = current_user_factory(get_db)


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
    settings = get_settings()
    return {
        "status": "ok",
        # True while outbound email goes to the in-process simulator
        # instead of real companies. The UI shows a sandbox banner.
        "sandbox": settings.email_provider == "mock",
    }


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
    # Claim types the agent can pursue against this company (from verified
    # policies). Empty for assist-mode-only companies.
    claim_types: list[str]
    # Internal targeting intelligence (goodwill range, best channel).
    intel: dict[str, Any] = {}


from karenbot.domain import categories as category_catalog  # noqa: E402

GENERAL_CATEGORIES = [c.key for c in category_catalog.GENERAL]


@app.get("/companies", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db)) -> list[CompanyOut]:
    from karenbot.domain.models import CompanyPolicy

    policy_types: dict[uuid.UUID, list[str]] = {}
    for policy in db.scalars(select(CompanyPolicy).where(CompanyPolicy.verified_at.is_not(None))):
        claim = (policy.eligibility_rules or {}).get("claim_type")
        if claim:
            policy_types.setdefault(policy.company_id, []).append(claim)
    return [
        CompanyOut(
            id=c.id,
            name=c.name,
            industry=c.industry,
            size_class=c.size_class,
            targetable=services.company_is_targetable(c),
            refuses_third_party=c.refuses_third_party,
            claim_types=sorted(set(policy_types.get(c.id, []))),
            intel=c.intel or {},
        )
        for c in db.scalars(select(Company).order_by(Company.name))
    ]


@app.get("/categories")
def general_categories() -> dict:
    """Category catalog: general plus industry-specific options with labels."""
    return {
        "general_categories": GENERAL_CATEGORIES,
        "general": [
            {"key": c.key, "label": c.label} for c in category_catalog.GENERAL
        ],
        "by_industry": {
            industry: [{"key": c.key, "label": c.label} for c in options]
            for industry, options in category_catalog.BY_INDUSTRY.items()
        },
        "industries": category_catalog.KNOWN_INDUSTRIES,
    }


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------


class CaseCreate(BaseModel):
    company_name: str
    category: str
    description: str
    requested_amount: Decimal | None = None
    incident_date: datetime | None = None
    # For unknown companies: what kind of business it is (drives the
    # suggested-category catalog and future classification review).
    company_industry: str | None = None


class CaseOut(BaseModel):
    id: uuid.UUID
    status: str
    category: str
    description: str
    requested_amount: Decimal | None
    currency: str
    contact_mode: str = "agent"
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
    name = payload.company_name.strip()
    if not name:
        raise HTTPException(422, "company name is required")
    category = payload.category.strip().lower().replace(" ", "_")[:80]
    if not category:
        raise HTTPException(422, "category is required")
    payload.category = category
    company = db.scalars(select(Company).where(Company.name == name)).first()
    if company is None:
        # Any company works: unknown ones start unclassified, which routes
        # the case to assist mode (Karen drafts; the customer sends). Agent
        # contact requires a human-verified channel first (moral code +
        # never-invent-addresses rule).
        industry = (payload.company_industry or "other").strip().lower()
        if industry not in category_catalog.KNOWN_INDUSTRIES:
            industry = "other"
        company = Company(name=name, industry=industry, size_class="unclassified")
        db.add(company)
        db.flush()
    case = services.create_case(
        db,
        user=user,
        company=company,
        category=payload.category,
        description=payload.description,
        requested_amount=payload.requested_amount,
        incident_date=payload.incident_date,
        assist_mode_ok=True,
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


class EvidenceItemOut(BaseModel):
    id: uuid.UUID
    evidence_type: str
    summary: str | None
    source: str

    model_config = {"from_attributes": True}


@app.get("/cases/{case_id}/evidence", response_model=list[EvidenceItemOut])
def list_evidence(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    case = _owned_case(db, case_id, user)
    from karenbot.domain.models import CaseEvidence

    return list(
        db.scalars(
            select(CaseEvidence)
            .where(CaseEvidence.case_id == case.id)
            .order_by(CaseEvidence.created_at)
        )
    )


@app.delete("/cases/{case_id}/evidence/{evidence_id}")
def remove_evidence(
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    case = _owned_case(db, case_id, user)
    from karenbot.domain.enums import ActorType
    from karenbot.domain.models import AuditEvent, CaseEvidence

    evidence = db.get(CaseEvidence, evidence_id)
    if evidence is None or evidence.case_id != case.id:
        raise HTTPException(404, "evidence not found")
    db.add(
        AuditEvent(
            actor_type=ActorType.CUSTOMER.value,
            actor_id=str(user.id),
            case_id=case.id,
            event_type="evidence.removed",
            event_payload={"evidence_id": str(evidence_id), "summary": (evidence.summary or "")[:120]},
        )
    )
    db.delete(evidence)
    return {"removed": str(evidence_id)}


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
    acceptance_queued = False
    if row.action_type == "accept_offer":
        # Close the loop with the company: accepted, receipts available.
        from karenbot.domain.models import RecoveryOutcome

        outcome = db.scalars(
            select(RecoveryOutcome)
            .where(RecoveryOutcome.case_id == case.id)
            .order_by(RecoveryOutcome.created_at.desc())
        ).first()
        if case.contact_mode == "agent":
            decision = _runtime.send_acceptance_confirmation(
                db, case, outcome.amount if outcome else None
            )
            acceptance_queued = decision.allowed
    return {"status": case.status, "acceptance_queued": acceptance_queued}


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

from karenbot.api import admin, banking, connect, scan  # noqa: E402

app.include_router(connect.build_router(), prefix="/connect", tags=["connect"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(banking.build_router(lambda: _runtime), prefix="/banking", tags=["banking"])
app.include_router(scan.build_router(), prefix="/scan", tags=["scan"])

if get_settings().dev_mode:
    from karenbot.api import dev

    # Getters so tests/dev tooling can swap the live instances.
    app.include_router(
        dev.build_router(lambda: _adapter, lambda: _worker), prefix="/dev", tags=["dev"]
    )
