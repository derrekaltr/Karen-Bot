"""Group inbox evidence hits into trips/orders so cases only attach what's
actually theirs.

Airlines stamp every email with a record locator ("Confirmation code:
QUWSMF"); retailers use order numbers. Hits sharing a locator form a group;
locator-less hits join a group when their date sits within a few days of it.
If a case's own text names a locator (or only one group exists), that group
auto-attaches; otherwise the user is asked which group the case is about.
"""

import re
from dataclasses import dataclass, field
from datetime import timedelta

from karenbot.discovery.inbox_scan import EvidenceHit

LOCATOR_CONTEXT_RE = re.compile(
    r"(?:confirmation(?:\s+code)?|record\s+locator|booking\s+reference|order)"
    r"\s*[:#]?\s*([A-Z0-9]{6,10})\b",
    re.IGNORECASE,
)
SUBJECT_SUFFIX_RE = re.compile(r"[-–]\s*([A-Z]{6})\b")

# Six-letter words that look like locators but aren't.
NOT_LOCATORS = {
    "UPDATE", "CANCEL", "REFUND", "FLIGHT", "TRAVEL", "STATUS", "ONLINE",
    "PLEASE", "THANKS", "MANAGE", "MOBILE", "NUMBER", "SUMMER", "WINTER",
}

DATE_CLUSTER_DAYS = 3


def extract_locator(text: str) -> str | None:
    for match in LOCATOR_CONTEXT_RE.finditer(text):
        token = match.group(1).upper()
        if token not in NOT_LOCATORS and not token.isdigit():
            return token
    for match in SUBJECT_SUFFIX_RE.finditer(text):
        token = match.group(1).upper()
        if token not in NOT_LOCATORS:
            return token
    return None


@dataclass
class EvidenceGroup:
    key: str  # locator, or "other"
    label: str
    hits: list[EvidenceHit] = field(default_factory=list)


def group_hits(hits: list[EvidenceHit]) -> list[EvidenceGroup]:
    by_locator: dict[str, list[EvidenceHit]] = {}
    unassigned: list[EvidenceHit] = []
    for hit in hits:
        locator = extract_locator(f"{hit.summary} {hit.snippet}")
        if locator:
            by_locator.setdefault(locator, []).append(hit)
        else:
            unassigned.append(hit)

    # Date-cluster locator-less hits into the nearest group.
    still_unassigned: list[EvidenceHit] = []
    for hit in unassigned:
        placed = False
        for members in by_locator.values():
            if any(
                abs(hit.occurred_at - m.occurred_at) <= timedelta(days=DATE_CLUSTER_DAYS)
                for m in members
            ):
                members.append(hit)
                placed = True
                break
        if not placed:
            still_unassigned.append(hit)

    groups: list[EvidenceGroup] = []
    for locator, members in by_locator.items():
        members.sort(key=lambda h: h.occurred_at)
        dates = f"{members[0].occurred_at:%b %d}"
        if members[-1].occurred_at.date() != members[0].occurred_at.date():
            dates += f"–{members[-1].occurred_at:%b %d, %Y}"
        else:
            dates += f", {members[0].occurred_at:%Y}"
        groups.append(
            EvidenceGroup(
                key=locator,
                label=f"Trip/order {locator} ({dates}, {len(members)} emails)",
                hits=members,
            )
        )
    if still_unassigned:
        groups.append(
            EvidenceGroup(
                key="other",
                label=f"Other emails ({len(still_unassigned)})",
                hits=sorted(still_unassigned, key=lambda h: h.occurred_at),
            )
        )
    groups.sort(key=lambda g: max(h.occurred_at for h in g.hits), reverse=True)
    return groups


def match_group_to_case(groups: list[EvidenceGroup], case_text: str) -> EvidenceGroup | None:
    """Auto-select a group only when the choice is unambiguous."""
    real_groups = [g for g in groups if g.key != "other"]
    if len(groups) == 1:
        return groups[0]
    upper = case_text.upper()
    named = [g for g in real_groups if g.key in upper]
    if len(named) == 1:
        return named[0]
    if not real_groups and len(groups) == 1:
        return groups[0]
    return None
