from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Size classes that may NEVER be targeted, regardless of configuration.
NEVER_TARGETABLE_SIZE_CLASSES = frozenset({"small_business", "unclassified"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KARENBOT_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://karenbot:karenbot@localhost:5432/karenbot"
    # Email provider for outbound/inbound mail. Multi-provider by design:
    # mock (dev) | gmail | outlook | imap_smtp — see channels/registry.py.
    email_provider: str = "mock"
    anthropic_api_key: str = ""
    llm_provider: str = "scripted"  # "scripted" | "anthropic"
    agent_model: str = "claude-sonnet-5-5"
    classifier_model: str = "claude-haiku-4-5"

    # Outbound disclosure wording. "representative" discloses the agency
    # relationship ("on behalf of X, who has authorized this
    # correspondence") without the KarenBot brand string — which is a
    # trivially filterable blocklist key for companies. "branded" adds the
    # product name. Both are honest; neither ever denies automation if
    # asked (enforced in prompts). Wording is on the attorney checklist.
    disclosure_mode: str = "representative"  # representative | branded

    # Moral code: company size classes KarenBot may target. Mom-and-pop
    # businesses ("small_business") and unreviewed companies ("unclassified")
    # must never appear here.
    targetable_size_classes: list[str] = ["enterprise"]

    # Global safety limits (per-case limits live in case authorizations)
    max_outbound_per_case_per_day: int = 3
    max_outbound_per_case_total: int = 12
    max_follow_ups: int = 4
    min_hours_between_outbound: int = 20
    # Cross-case limits: one user across all their cases, and the whole
    # platform (circuit breaker against runaway sending).
    max_outbound_per_user_per_day: int = 10
    max_outbound_global_per_hour: int = 100

    # Admin API token (dev default only works in dev mode).
    admin_token: str = "dev-admin"

    # Clerk authentication. The publishable key also encodes the frontend API
    # domain (used to derive the JWKS URL); jwks_url overrides if set.
    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_jwks_url: str = ""
    # Dev-mode fallback: allow the X-User-Email header instead of a session
    # JWT. Hard-disabled outside dev mode regardless of this setting.
    allow_dev_auth: bool = True

    # Observability (optional).
    sentry_dsn: str = ""

    # Plaid (recurring-bill discovery). env: mock | sandbox | production.
    plaid_env: str = "mock"
    plaid_client_id: str = ""
    plaid_secret: str = ""

    # Worker
    worker_poll_seconds: float = 2.0
    outbox_sending_lease_seconds: int = 300

    # Enables the /dev router (seed data, simulated company replies). Must be
    # false in any deployed environment.
    dev_mode: bool = True

    # Fernet key for OAuth tokens at rest (python -m karenbot.security.crypto
    # to generate). Required outside dev mode.
    token_encryption_key: str = ""

    # OAuth clients for email providers. Empty = provider connect disabled.
    google_client_id: str = ""
    google_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    oauth_redirect_base: str = "http://localhost:8000"

    # Sender identity for SMTP/IMAP accounts (per-account overrides live on
    # the connected account's token payload).
    outbound_from_name: str = "KarenBot (authorized representative)"

    @field_validator("targetable_size_classes")
    @classmethod
    def _enforce_moral_code(cls, value: list[str]) -> list[str]:
        # The moral code is not configurable away: small businesses and
        # unreviewed companies are silently stripped if anyone adds them.
        return [v for v in value if v not in NEVER_TARGETABLE_SIZE_CLASSES]


@lru_cache
def get_settings() -> Settings:
    return Settings()
