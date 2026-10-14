"""Moral code: KarenBot never goes after mom-and-pop businesses.

Enforced in three independent layers:
1. Case creation refuses non-targetable companies (tested here).
2. The policy engine denies outbound actions to them (tests/policy/test_engine.py).
3. Configuration cannot whitelist them (tested here).
"""

from decimal import Decimal

import pytest

from karenbot import services
from karenbot.domain.models import Company, User


def _mk(session, size_class: str) -> tuple[User, Company]:
    user = User(email=f"u-{size_class}@example.com")
    company = Company(name=f"Co-{size_class}", industry="restaurant", size_class=size_class)
    session.add_all([user, company])
    session.flush()
    return user, company


@pytest.mark.parametrize("size_class", ["small_business", "unclassified", "mid_market"])
def test_case_creation_refused_for_untargetable_company(db, size_class):
    with db() as session:
        user, company = _mk(session, size_class)
        with pytest.raises(services.CompanyNotTargetable):
            services.create_case(
                session,
                user=user,
                company=company,
                category="refund",
                description="x",
                requested_amount=Decimal("50"),
            )


def test_case_creation_allowed_for_enterprise(db):
    with db() as session:
        user, company = _mk(session, "enterprise")
        case = services.create_case(
            session,
            user=user,
            company=company,
            category="refund",
            description="x",
            requested_amount=Decimal("50"),
        )
        assert case.id is not None


def test_config_cannot_whitelist_small_business(monkeypatch):
    monkeypatch.setenv(
        "KARENBOT_TARGETABLE_SIZE_CLASSES",
        '["enterprise", "small_business", "unclassified"]',
    )
    from karenbot.config import get_settings

    get_settings.cache_clear()
    try:
        assert "small_business" not in get_settings().targetable_size_classes
        assert "unclassified" not in get_settings().targetable_size_classes
        assert "enterprise" in get_settings().targetable_size_classes
    finally:
        get_settings.cache_clear()
