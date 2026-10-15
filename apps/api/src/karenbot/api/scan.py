"""Scan API: find claimable situations in email; attach matching evidence.

User-initiated only (buttons, not background jobs). Candidates become
normal cases via the standard intake path; evidence hits become
CaseEvidence rows with source=email_scan.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.discovery.inbox_scan import get_inbox_scanner
from karenbot.domain.enums import ActorType
from karenbot.domain.models import AuditEvent, Case, CaseEvidence, User


class CandidateOut(BaseModel):
    kind: str
    company_name: str
    company_industry: str
    suggested_category: str
    title: str
    snippet: str
    amount: Decimal | None
    occurred_at: datetime
    reference: str


class EvidenceOut(BaseModel):
    id: uuid.UUID
    evidence_type: str
    summary: str


class InboxScanOut(BaseModel):
    # "mock" = simulated demo inbox; "live" = the user's real connected
    # mailbox. The UI labels demo results honestly.
    source: str
    candidates: list[CandidateOut]


class EvidenceScanOut(BaseModel):
    source: str
    attached: list[EvidenceOut]
    # Total matches including ones attached by earlier scans, so the UI can
    # say "nothing NEW" instead of pretending nothing exists.
    total_matches: int


def build_router() -> APIRouter:
    from karenbot.api.main import current_user, get_db

    router = APIRouter()

    @router.post("/inbox", response_model=InboxScanOut)
    def scan_inbox(
        user: User = Depends(current_user), db: Session = Depends(get_db)
    ) -> InboxScanOut:
        try:
            scanner = get_inbox_scanner()
        except NotImplementedError as exc:
            raise HTTPException(503, str(exc)) from exc
        from karenbot.discovery.inbox_scan import MockInboxScanner

        source = "mock" if isinstance(scanner, MockInboxScanner) else "live"
        candidates = scanner.scan_claims()
        db.add(
            AuditEvent(
                actor_type=ActorType.CUSTOMER.value,
                actor_id=str(user.id),
                event_type="scan.inbox_claims",
                event_payload={"candidates_found": len(candidates)},
            )
        )
        # Don't resurface things the user already turned into cases: match
        # on company + category of their existing cases.
        existing = {
            (c.category, str(c.company_id))
            for c in db.scalars(select(Case).where(Case.user_id == user.id))
        }
        from karenbot.domain.models import Company

        out = []
        for candidate in candidates:
            company = db.scalars(
                select(Company).where(Company.name == candidate.company_name)
            ).first()
            if company and (candidate.suggested_category, str(company.id)) in existing:
                continue
            out.append(CandidateOut(**candidate.__dict__))
        return InboxScanOut(source=source, candidates=out)

    @router.post("/cases/{case_id}/evidence", response_model=EvidenceScanOut)
    def scan_case_evidence(
        case_id: uuid.UUID,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> EvidenceScanOut:
        case = db.get(Case, case_id)
        if case is None or case.user_id != user.id:
            raise HTTPException(404, "case not found")
        try:
            scanner = get_inbox_scanner()
        except NotImplementedError as exc:
            raise HTTPException(503, str(exc)) from exc
        from karenbot.discovery.inbox_scan import MockInboxScanner

        source = "mock" if isinstance(scanner, MockInboxScanner) else "live"
        company = case.company
        keywords = [case.category, *case.category.split("_")]
        hits = scanner.find_evidence(company.name, keywords)

        # Idempotent on the scan reference.
        existing_refs = {
            e.encrypted_storage_reference
            for e in db.scalars(select(CaseEvidence).where(CaseEvidence.case_id == case.id))
        }
        added: list[CaseEvidence] = []
        for hit in hits:
            if f"scan:{hit.reference}" in existing_refs:
                continue
            evidence = CaseEvidence(
                case_id=case.id,
                evidence_type="email_scan",
                summary=f"{hit.summary} — {hit.snippet}"[:1000],
                source="email_scan",
                encrypted_storage_reference=f"scan:{hit.reference}",
            )
            db.add(evidence)
            added.append(evidence)
        db.flush()
        db.add(
            AuditEvent(
                actor_type=ActorType.CUSTOMER.value,
                actor_id=str(user.id),
                case_id=case.id,
                event_type="scan.evidence_attached",
                event_payload={"hits": len(added), "total_matches": len(hits)},
            )
        )
        return EvidenceScanOut(
            source=source,
            attached=[EvidenceOut.model_validate(e, from_attributes=True) for e in added],
            total_matches=len(hits),
        )

    return router
