"""Research public claimable events (outages, disruptions, recalls).

The LLM searches the public web and proposes ResearchedEvents; everything it
returns is inserted as a DRAFT ClaimEvent. Nothing is user-visible until a
human publishes it in /admin — that approval gate is also the injection
checkpoint for web-derived text. Entitlements are grounded in our verified
CompanyPolicy records, which are passed into the prompt as context.
"""

import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.agent.prompts import load_prompt
from karenbot.agent.schemas import ResearchedEvent, ResearchedEvents
from karenbot.domain import categories as category_catalog
from karenbot.domain.models import ClaimEvent, Company, CompanyPolicy

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS = 7


class _LLM(Protocol):
    def generate(
        self, task: str, system_prompt: str, user_content: str, output_model: type
    ) -> BaseModel: ...


def _known_claim_types() -> list[str]:
    keys = {c.key for c in category_catalog.GENERAL}
    for options in category_catalog.BY_INDUSTRY.values():
        keys.update(c.key for c in options)
    return sorted(keys)


def _policy_context(db: Session) -> list[dict[str, Any]]:
    """Compact verified-policy summaries the prompt can ground entitlements in."""
    rows = []
    for policy in db.scalars(
        select(CompanyPolicy).where(CompanyPolicy.verified_at.is_not(None))
    ):
        company = db.get(Company, policy.company_id)
        rows.append(
            {
                "company": company.name if company else "",
                "claim_type": (policy.eligibility_rules or {}).get("claim_type"),
                "summary": (policy.content or {}).get("summary", ""),
            }
        )
    return rows


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _usable(event: ResearchedEvent, lookback_days: int) -> bool:
    event_date = _parse_date(event.event_date)
    if event_date is None or not event.source_urls:
        return False
    today = datetime.now(UTC).date()
    window_start = today - timedelta(days=lookback_days + 3)  # small slack
    return window_start <= event_date <= today


def research_claim_events(
    db: Session, llm: _LLM, lookback_days: int = DEFAULT_LOOKBACK_DAYS
) -> dict[str, int]:
    """Run the research task and insert draft ClaimEvents. Returns counts."""
    system_prompt, prompt_version = load_prompt("research_events")
    system_prompt = system_prompt.replace("{lookback_days}", str(lookback_days))
    context = {
        "lookback_days": lookback_days,
        "today": datetime.now(UTC).date().isoformat(),
        "claim_type_keys": _known_claim_types(),
        "verified_policies": _policy_context(db),
    }
    user_content = json.dumps(context)

    generate = getattr(llm, "generate_with_search", None) or llm.generate
    result = generate(
        task="research_events",
        system_prompt=system_prompt,
        user_content=user_content,
        output_model=ResearchedEvents,
    )
    assert isinstance(result, ResearchedEvents)

    existing = {
        (e.company_name.lower(), e.event_date, e.category)
        for e in db.scalars(select(ClaimEvent))
    }
    companies_by_name = {c.name.lower(): c for c in db.scalars(select(Company))}

    created = 0
    skipped = 0
    for event in result.events:
        if not _usable(event, lookback_days):
            skipped += 1
            continue
        event_date = _parse_date(event.event_date)
        assert event_date is not None  # _usable guarantees it
        key = (event.company_name.lower(), event_date, event.category)
        if key in existing:
            skipped += 1
            continue
        company = companies_by_name.get(event.company_name.lower())
        db.add(
            ClaimEvent(
                company_id=company.id if company else None,
                company_name=event.company_name,
                title=event.title[:300],
                summary=event.summary,
                event_date=event_date,
                region=event.region,
                entitlement=event.entitlement,
                eligibility=event.eligibility,
                how_to_claim=event.how_to_claim,
                claim_deadline=_parse_date(event.claim_deadline),
                category=event.category,
                source_urls=event.source_urls,
                status="draft",
                created_by="research_agent",
                research_notes="\n".join(
                    part
                    for part in (f"confidence: {event.confidence}", event.notes)
                    if part
                ),
            )
        )
        existing.add(key)
        created += 1
    logger.info(
        "event research (%s): %d drafts created, %d skipped", prompt_version, created, skipped
    )
    return {"created": created, "skipped": skipped, "proposed": len(result.events)}
