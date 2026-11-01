"""Ops Council API: the company's internal operating layer.

Everything is an OpsItem (design concept, proposal, task, decision, research
brief) with one uniform flow: submitter -> reviewer -> approved |
changes_requested, plus a comment thread. Access requires a normal Clerk
login whose email is on the ops_members allowlist — built for teammates who
are not AI-literate, so the surface is forms and buttons, not prompts.
"""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.agent.prompts import load_prompt
from karenbot.agent.schemas import BusinessBriefs
from karenbot.domain.enums import ActorType
from karenbot.domain.models import (
    AuditEvent,
    OpsComment,
    OpsItem,
    OpsMember,
    User,
    utcnow,
)

ITEM_KINDS = ("design_concept", "proposal", "task", "decision", "research_brief")
RESEARCH_AUTHOR = "karen-research"


class MemberOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str

    model_config = {"from_attributes": True}


class MemberIn(BaseModel):
    email: str
    display_name: str
    role: str = "member"


class CommentOut(BaseModel):
    id: uuid.UUID
    author_email: str
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ItemOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str
    status: str
    created_by_email: str
    reviewer_email: str | None
    recommendation: str | None
    source_urls: list[str]
    decided_at: datetime | None
    created_at: datetime
    comment_count: int = 0


class ItemDetailOut(ItemOut):
    comments: list[CommentOut]


class ItemIn(BaseModel):
    kind: str
    title: str
    body: str
    reviewer_email: str | None = None


class CommentIn(BaseModel):
    body: str


class DecisionIn(BaseModel):
    comment: str | None = None


def _item_out(item: OpsItem, comment_count: int | None = None) -> ItemOut:
    return ItemOut(
        id=item.id,
        kind=item.kind,
        title=item.title,
        body=item.body,
        status=item.status,
        created_by_email=item.created_by_email,
        reviewer_email=item.reviewer_email,
        recommendation=item.recommendation,
        source_urls=item.source_urls or [],
        decided_at=item.decided_at,
        created_at=item.created_at,
        comment_count=(
            comment_count if comment_count is not None else len(item.comments)
        ),
    )


def build_router() -> APIRouter:
    from karenbot.api.main import current_user, get_db

    router = APIRouter()

    def current_member(
        user: User = Depends(current_user), db: Session = Depends(get_db)
    ) -> OpsMember:
        member = db.scalars(
            select(OpsMember).where(OpsMember.email == user.email)
        ).first()
        if member is None:
            raise HTTPException(
                403,
                "not an ops member — ask an owner to add you on the Team tab",
            )
        return member

    def require_owner(member: OpsMember = Depends(current_member)) -> OpsMember:
        if member.role != "owner":
            raise HTTPException(403, "owners only")
        return member

    # ---- membership -------------------------------------------------------

    @router.get("/me", response_model=MemberOut)
    def me(member: OpsMember = Depends(current_member)) -> OpsMember:
        return member

    @router.get("/members", response_model=list[MemberOut])
    def members(
        member: OpsMember = Depends(current_member),
        db: Session = Depends(get_db),
    ) -> list[OpsMember]:
        return list(db.scalars(select(OpsMember).order_by(OpsMember.created_at)))

    @router.post("/members", response_model=MemberOut)
    def add_member(
        payload: MemberIn,
        owner: OpsMember = Depends(require_owner),
        db: Session = Depends(get_db),
    ) -> OpsMember:
        email = payload.email.strip().lower()
        if not email or "@" not in email:
            raise HTTPException(422, "a valid email is required")
        if payload.role not in ("owner", "member"):
            raise HTTPException(422, "role must be owner or member")
        existing = db.scalars(select(OpsMember).where(OpsMember.email == email)).first()
        if existing is not None:
            return existing
        member = OpsMember(
            email=email,
            display_name=payload.display_name.strip() or email.split("@")[0],
            role=payload.role,
            added_by=owner.email,
        )
        db.add(member)
        db.flush()
        db.add(
            AuditEvent(
                actor_type=ActorType.CUSTOMER.value,
                actor_id=owner.email,
                event_type="ops.member_added",
                event_payload={"email": email, "role": payload.role},
            )
        )
        return member

    # ---- items ------------------------------------------------------------

    @router.get("/items", response_model=list[ItemOut])
    def items(
        box: str = "all",  # all | inbox | sent | research
        member: OpsMember = Depends(current_member),
        db: Session = Depends(get_db),
    ) -> list[ItemOut]:
        query = select(OpsItem).order_by(OpsItem.created_at.desc())
        if box == "inbox":
            query = query.where(
                OpsItem.reviewer_email == member.email,
                OpsItem.status == "in_review",
            )
        elif box == "sent":
            query = query.where(OpsItem.created_by_email == member.email)
        elif box == "research":
            query = query.where(OpsItem.kind == "research_brief")
        return [_item_out(i) for i in db.scalars(query)]

    @router.post("/items", response_model=ItemOut)
    def create_item(
        payload: ItemIn,
        member: OpsMember = Depends(current_member),
        db: Session = Depends(get_db),
    ) -> ItemOut:
        if payload.kind not in ITEM_KINDS:
            raise HTTPException(422, f"kind must be one of {ITEM_KINDS}")
        if not payload.title.strip() or not payload.body.strip():
            raise HTTPException(422, "title and description are required")
        reviewer = (payload.reviewer_email or "").strip().lower() or None
        if reviewer is not None:
            known = db.scalars(
                select(OpsMember).where(OpsMember.email == reviewer)
            ).first()
            if known is None:
                raise HTTPException(422, "reviewer must be an ops member")
        item = OpsItem(
            kind=payload.kind,
            title=payload.title.strip()[:300],
            body=payload.body.strip(),
            status="in_review" if reviewer else "new",
            created_by_email=member.email,
            reviewer_email=reviewer,
        )
        db.add(item)
        db.flush()
        db.add(
            AuditEvent(
                actor_type=ActorType.CUSTOMER.value,
                actor_id=member.email,
                event_type="ops.item_created",
                event_payload={
                    "item_id": str(item.id),
                    "kind": item.kind,
                    "reviewer": reviewer,
                },
            )
        )
        return _item_out(item, comment_count=0)

    @router.get("/items/{item_id}", response_model=ItemDetailOut)
    def item_detail(
        item_id: uuid.UUID,
        member: OpsMember = Depends(current_member),
        db: Session = Depends(get_db),
    ) -> ItemDetailOut:
        item = db.get(OpsItem, item_id)
        if item is None:
            raise HTTPException(404, "item not found")
        base = _item_out(item)
        return ItemDetailOut(
            **base.model_dump(),
            comments=[
                CommentOut.model_validate(c, from_attributes=True)
                for c in item.comments
            ],
        )

    @router.post("/items/{item_id}/comments", response_model=CommentOut)
    def add_comment(
        item_id: uuid.UUID,
        payload: CommentIn,
        member: OpsMember = Depends(current_member),
        db: Session = Depends(get_db),
    ) -> OpsComment:
        item = db.get(OpsItem, item_id)
        if item is None:
            raise HTTPException(404, "item not found")
        if not payload.body.strip():
            raise HTTPException(422, "comment is empty")
        comment = OpsComment(
            item_id=item.id, author_email=member.email, body=payload.body.strip()
        )
        db.add(comment)
        db.flush()
        return comment

    def _decide(
        db: Session,
        member: OpsMember,
        item_id: uuid.UUID,
        new_status: str,
        comment: str | None,
    ) -> OpsItem:
        item = db.get(OpsItem, item_id)
        if item is None:
            raise HTTPException(404, "item not found")
        if item.reviewer_email != member.email:
            raise HTTPException(403, "only the assigned reviewer can decide")
        if item.status not in ("in_review", "changes_requested"):
            raise HTTPException(409, f"item is {item.status}")
        item.status = new_status
        item.decided_at = utcnow()
        if comment and comment.strip():
            db.add(
                OpsComment(
                    item_id=item.id, author_email=member.email, body=comment.strip()
                )
            )
        db.add(
            AuditEvent(
                actor_type=ActorType.CUSTOMER.value,
                actor_id=member.email,
                event_type=f"ops.item_{new_status}",
                event_payload={"item_id": str(item.id), "title": item.title},
            )
        )
        db.flush()
        return item

    @router.post("/items/{item_id}/approve", response_model=ItemOut)
    def approve_item(
        item_id: uuid.UUID,
        payload: DecisionIn,
        member: OpsMember = Depends(current_member),
        db: Session = Depends(get_db),
    ) -> ItemOut:
        return _item_out(_decide(db, member, item_id, "approved", payload.comment))

    @router.post("/items/{item_id}/request-changes", response_model=ItemOut)
    def request_changes(
        item_id: uuid.UUID,
        payload: DecisionIn,
        member: OpsMember = Depends(current_member),
        db: Session = Depends(get_db),
    ) -> ItemOut:
        return _item_out(
            _decide(db, member, item_id, "changes_requested", payload.comment)
        )

    @router.post("/items/{item_id}/resubmit", response_model=ItemOut)
    def resubmit(
        item_id: uuid.UUID,
        member: OpsMember = Depends(current_member),
        db: Session = Depends(get_db),
    ) -> ItemOut:
        """After addressing requested changes, send it back for review."""
        item = db.get(OpsItem, item_id)
        if item is None:
            raise HTTPException(404, "item not found")
        if item.created_by_email != member.email:
            raise HTTPException(403, "only the submitter can resubmit")
        if item.status != "changes_requested":
            raise HTTPException(409, f"item is {item.status}")
        item.status = "in_review"
        db.flush()
        return _item_out(item)

    # ---- research agent ---------------------------------------------------

    @router.post("/research/run")
    def run_research(
        focus: str | None = None,
        member: OpsMember = Depends(current_member),
        db: Session = Depends(get_db),
    ) -> dict[str, int]:
        """Run the business-research agent now; briefs land as items."""
        from karenbot.api.main import _llm

        llm = _llm()
        system_prompt, prompt_version = load_prompt("business_research")
        context = {
            "today": utcnow().date().isoformat(),
            "focus_areas": focus
            or (
                "competitors (Rocket Money, DoNotPay, claims services), consumer-"
                "protection regulation (DOT, FTC, state UPL rules), payment/"
                "banking vendor news (Plaid, Stripe), and distribution ideas"
            ),
            "company": (
                "KarenBot: AI consumer-recovery platform — negotiates refunds and "
                "compensation with large companies, cancels subscriptions, "
                "surfaces claimable public events. Pre-launch, two founders."
            ),
        }
        generate = getattr(llm, "generate_with_search", None) or llm.generate
        result = generate(
            task="business_research",
            system_prompt=system_prompt,
            user_content=json.dumps(context),
            output_model=BusinessBriefs,
        )
        assert isinstance(result, BusinessBriefs)
        existing_titles = {
            i.title
            for i in db.scalars(select(OpsItem).where(OpsItem.kind == "research_brief"))
        }
        created = 0
        for brief in result.briefs:
            if not brief.source_urls or brief.title in existing_titles:
                continue
            db.add(
                OpsItem(
                    kind="research_brief",
                    title=brief.title[:300],
                    body=f"{brief.summary}\n\nWhy it matters: {brief.why_it_matters}",
                    status="new",
                    created_by_email=RESEARCH_AUTHOR,
                    recommendation=brief.recommendation,
                    source_urls=brief.source_urls,
                )
            )
            created += 1
        db.add(
            AuditEvent(
                actor_type=ActorType.CUSTOMER.value,
                actor_id=member.email,
                event_type="ops.research_run",
                event_payload={
                    "prompt_version": prompt_version,
                    "proposed": len(result.briefs),
                    "created": created,
                },
            )
        )
        return {"proposed": len(result.briefs), "created": created}

    return router
