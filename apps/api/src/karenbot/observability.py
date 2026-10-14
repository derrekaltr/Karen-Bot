"""Observability bootstrap: structured logging + optional Sentry.

Called from both entrypoints (API app, worker). Sentry activates only when
KARENBOT_SENTRY_DSN is set and sentry-sdk is installed (it ships in the
`observability` extra). OpenTelemetry tracing is a planned follow-up; the
audit log remains the system of record for agent behavior either way.
"""

import logging

from karenbot.config import get_settings

_initialized = False


def init_observability(service_name: str) -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s %(levelname)s [{service_name}] %(name)s: %(message)s",
    )

    dsn = get_settings().sentry_dsn
    if dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=dsn, traces_sample_rate=0.1, environment=service_name)
            logging.getLogger(__name__).info("sentry initialized")
        except ImportError:
            logging.getLogger(__name__).warning(
                "KARENBOT_SENTRY_DSN set but sentry-sdk not installed; "
                "pip install 'karenbot-api[observability]'"
            )
