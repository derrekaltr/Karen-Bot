"""Email/channel provider registry.

KarenBot is not Gmail-only: every provider implements the same
ChannelAdapter protocol and is selected per connected account
(`connected_accounts.provider`). Planned provider coverage:

- "mock"      — in-process simulator (dev/tests); implemented.
- "gmail"     — Gmail API via Google OAuth (restricted scopes); M4.
- "outlook"   — Microsoft Graph: Outlook.com, Hotmail, Microsoft 365; M4.
- "imap_smtp" — generic IMAP/SMTP with OAuth or app passwords: Yahoo,
                iCloud, Fastmail, custom domains; M4. The long tail.

Adding a provider must never touch the agent, policy, or workflow layers —
if it does, the abstraction has failed.
"""

from collections.abc import Callable

from karenbot.channels.base import ChannelAdapter
from karenbot.channels.mock_email import MockEmailAdapter

AdapterFactory = Callable[[], ChannelAdapter]


def _unimplemented(provider: str, milestone: str) -> AdapterFactory:
    def factory() -> ChannelAdapter:
        raise NotImplementedError(
            f"email provider '{provider}' is scheduled for {milestone}; "
            "use 'mock' for local development"
        )

    return factory


EMAIL_PROVIDERS: dict[str, AdapterFactory] = {
    "mock": MockEmailAdapter,
    "gmail": _unimplemented("gmail", "M4"),
    "outlook": _unimplemented("outlook", "M4"),
    "imap_smtp": _unimplemented("imap_smtp", "M4"),
}


def get_email_adapter(provider: str) -> ChannelAdapter:
    try:
        return EMAIL_PROVIDERS[provider]()
    except KeyError:
        raise ValueError(
            f"unknown email provider '{provider}'; known: {sorted(EMAIL_PROVIDERS)}"
        ) from None
