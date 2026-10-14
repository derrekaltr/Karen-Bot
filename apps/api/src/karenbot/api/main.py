"""KarenBot API (MVP scaffold).

Auth is a dev stub (X-User-Email header) until Clerk JWT verification lands
in M3. Endpoints mirror the service layer; the agent/worker runs separately.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot import services
from karenbot.db.session import get_session_factory
from karenbot.domain.models import Case, Communication, Company, User

app = FastAPI(title="KarenBot API", version="0.1.0")


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
        raise HTTPException(401, "unknown user")
    return user


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


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

    model_config = {"from_attributes": True}


@app.post("/cases", response_model=CaseOut)
def create_case(
    payload: CaseCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Case:
    company = db.scalars(select(Company).where(Company.name == payload.company_name)).first()
    if company is None:
        raise HTTPException(404, "company not supported yet")
    if not services.company_is_targetable(company):
        raise HTTPException(
            422,
            "KarenBot only takes on large companies — this business is not "
            "one we'll go after.",
        )
    return services.create_case(
        db,
        user=user,
        company=company,
        category=payload.category,
        description=payload.description,
        requested_amount=payload.requested_amount,
        incident_date=payload.incident_date,
    )


@app.get("/cases/{case_id}", response_model=CaseOut)
def get_case(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Case:
    case = db.get(Case, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(404, "case not found")
    return case


class CommunicationOut(BaseModel):
    id: uuid.UUID
    channel: str
    direction: str
    counterparty: str
    subject: str | None
    body: str
    sent_at: datetime | None
    received_at: datetime | None

    model_config = {"from_attributes": True}


@app.get("/cases/{case_id}/communications", response_model=list[CommunicationOut])
def list_communications(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[Communication]:
    case = db.get(Case, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(404, "case not found")
    return list(
        db.scalars(
            select(Communication)
            .where(Communication.case_id == case_id)
            .order_by(Communication.created_at)
        )
    )


@app.post("/cases/{case_id}/revoke")
def revoke(
    case_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    case = db.get(Case, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(404, "case not found")
    services.revoke_authorization(db, case)
    return {"status": case.status}
