"""Plaid integration for recurring-bill discovery.

Three implementations of one protocol:
- PlaidHttpClient: real Plaid REST API (sandbox or production) over httpx.
  Uses /transactions/recurring/get, which does recurrence detection
  server-side.
- MockPlaidClient: canned data for local dev and tests (default).

Access tokens are never returned to the frontend and are stored
Fernet-encrypted on bank_connections. Production Plaid access requires
Plaid's approval process; sandbox works with free dev keys.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

import httpx

from karenbot.config import get_settings

PLAID_HOSTS = {
    "sandbox": "https://sandbox.plaid.com",
    "production": "https://production.plaid.com",
}

# Plaid frequency values -> our cadence vocabulary.
FREQUENCY_MAP = {
    "WEEKLY": "weekly",
    "BIWEEKLY": "weekly",
    "SEMI_MONTHLY": "monthly",
    "MONTHLY": "monthly",
    "ANNUALLY": "yearly",
}


@dataclass(frozen=True)
class RecurringStream:
    merchant_name: str
    amount: Decimal
    currency: str
    cadence: str  # weekly | monthly | yearly
    first_date: datetime | None
    last_date: datetime | None
    occurrences: int


@dataclass(frozen=True)
class LinkedItem:
    access_token: str
    item_id: str
    institution_name: str | None = None


class PlaidClient(Protocol):
    def create_link_token(self, user_id: str) -> str: ...

    def exchange_public_token(self, public_token: str) -> LinkedItem: ...

    def get_recurring(self, access_token: str) -> list[RecurringStream]: ...


class PlaidHttpClient:
    def __init__(self, http: httpx.Client | None = None):
        settings = get_settings()
        if settings.plaid_env not in PLAID_HOSTS:
            raise ValueError(f"plaid_env must be sandbox or production, got {settings.plaid_env}")
        if not settings.plaid_client_id or not settings.plaid_secret:
            raise RuntimeError("Plaid client id/secret are not configured")
        self.base = PLAID_HOSTS[settings.plaid_env]
        self.auth = {"client_id": settings.plaid_client_id, "secret": settings.plaid_secret}
        self.http = http or httpx.Client(timeout=30)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.http.post(f"{self.base}{path}", json={**self.auth, **payload})
        response.raise_for_status()
        return response.json()

    def create_link_token(self, user_id: str) -> str:
        data = self._post(
            "/link/token/create",
            {
                "client_name": "KarenBot",
                "user": {"client_user_id": user_id},
                "products": ["transactions"],
                "country_codes": ["US"],
                "language": "en",
            },
        )
        return data["link_token"]

    def exchange_public_token(self, public_token: str) -> LinkedItem:
        data = self._post("/item/public_token/exchange", {"public_token": public_token})
        return LinkedItem(access_token=data["access_token"], item_id=data["item_id"])

    def get_recurring(self, access_token: str) -> list[RecurringStream]:
        data = self._post("/transactions/recurring/get", {"access_token": access_token})
        streams: list[RecurringStream] = []
        for stream in data.get("outflow_streams", []):
            if stream.get("is_active") is False:
                continue
            cadence = FREQUENCY_MAP.get(stream.get("frequency", ""), None)
            if cadence is None:
                continue
            average = stream.get("average_amount", {})
            streams.append(
                RecurringStream(
                    merchant_name=stream.get("merchant_name")
                    or stream.get("description", "Unknown merchant"),
                    amount=Decimal(str(abs(average.get("amount", 0)))),
                    currency=average.get("iso_currency_code") or "USD",
                    cadence=cadence,
                    first_date=_parse_date(stream.get("first_date")),
                    last_date=_parse_date(stream.get("last_date")),
                    occurrences=len(stream.get("transaction_ids", [])),
                )
            )
        return streams


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


@dataclass
class MockPlaidClient:
    """Dev/test stand-in: a plausible pile of forgotten subscriptions."""

    streams: list[RecurringStream] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.streams:
            now = datetime.now(UTC)
            self.streams = [
                RecurringStream("Chipotle Rewards+", Decimal("9.99"), "USD", "monthly", None, now, 7),
                RecurringStream("StreamFlix", Decimal("22.99"), "USD", "monthly", None, now, 14),
                RecurringStream("GymCo Fitness", Decimal("44.00"), "USD", "monthly", None, now, 11),
                RecurringStream("CloudVault Pro", Decimal("119.00"), "USD", "yearly", None, now, 2),
                RecurringStream("Rosa's Coffee Club", Decimal("15.00"), "USD", "monthly", None, now, 5),
            ]

    def create_link_token(self, user_id: str) -> str:
        return f"link-mock-{user_id[:8]}"

    def exchange_public_token(self, public_token: str) -> LinkedItem:
        return LinkedItem(
            access_token=f"access-mock-{public_token[-6:]}",
            item_id=f"item-mock-{public_token[-6:]}",
            institution_name="Mock Bank of Dev",
        )

    def get_recurring(self, access_token: str) -> list[RecurringStream]:
        return list(self.streams)


def get_plaid_client() -> PlaidClient:
    if get_settings().plaid_env == "mock":
        return MockPlaidClient()
    return PlaidHttpClient()
