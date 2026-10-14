from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KARENBOT_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://karenbot:karenbot@localhost:5432/karenbot"
    anthropic_api_key: str = ""
    llm_provider: str = "scripted"  # "scripted" | "anthropic"
    agent_model: str = "claude-sonnet-5-5"
    classifier_model: str = "claude-haiku-4-5-20251001"

    # Global safety limits (per-case limits live in case authorizations)
    max_outbound_per_case_per_day: int = 3
    max_outbound_per_case_total: int = 12
    max_follow_ups: int = 4
    min_hours_between_outbound: int = 20

    # Worker
    worker_poll_seconds: float = 2.0
    outbox_sending_lease_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
