"""Email/channel provider registry.

KarenBot is not Gmail-only: every provider implements the same
ChannelAdapter protocol and is selected per connected account
(`connected_accounts.provider`):

- "mock"      — in-process simulator (dev/tests).
- "gmail"     — Gmail REST API via Google OAuth (restricted scopes).
- "outlook"   — Microsoft Graph: Outlook.com, Hotmail, Microsoft 365.
- "imap_smtp" — generic IMAP/SMTP with app passwords: Yahoo, iCloud,
                Fastmail, custom domains. The long tail.

Per-account adapter construction lives in channels/resolver.py. This module
only answers "which provider keys exist" plus the fixed-adapter dev path.
Adding a provider must never touch the agent, policy, or workflow layers —
if it does, the abstraction has failed.
"""

from karenbot.channels.base import ChannelAdapter
from karenbot.channels.mock_email import MockEmailAdapter

KNOWN_PROVIDERS = frozenset({"mock", "gmail", "outlook", "imap_smtp"})


def get_email_adapter(provider: str) -> ChannelAdapter:
    """Fixed-adapter path, used in dev/mock mode only. Real providers are
    account-scoped: use channels.resolver.build_adapter(account)."""
    if provider == "mock":
        return MockEmailAdapter()
    if provider in KNOWN_PROVIDERS:
        raise ValueError(
            f"provider '{provider}' is account-scoped; connect an account and "
            "use channels.resolver instead of a global adapter"
        )
    raise ValueError(f"unknown email provider '{provider}'; known: {sorted(KNOWN_PROVIDERS)}")
