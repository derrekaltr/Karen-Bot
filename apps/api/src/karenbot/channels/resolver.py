"""Resolve the right email adapter for a given account / outbox row.

Multi-provider by design: the adapter is chosen per connected account
(`connected_accounts.provider`), not globally. Token refreshes are persisted
back to the account row using a short-lived dedicated session, so a refresh
mid-delivery survives even if the delivery transaction rolls back.
"""

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.channels.base import ChannelAdapter
from karenbot.channels.gmail import GmailAdapter
from karenbot.channels.imap_smtp import ImapSmtpAdapter, ImapSmtpConfig
from karenbot.channels.oauth import TokenStore
from karenbot.channels.outlook import OutlookAdapter
from karenbot.db.session import get_session_factory
from karenbot.domain.models import Case, ConnectedAccount, OutboxMessage

EMAIL_OAUTH_PROVIDERS = {"gmail", "outlook"}


class NoConnectedAccount(Exception):
    pass


def _token_getter(account_id, provider: str) -> Callable[[], str]:
    """Returns a callable yielding a valid access token, persisting refreshes."""
    store = TokenStore(provider)

    def getter() -> str:
        factory = get_session_factory()
        with factory() as session:
            account = session.get(ConnectedAccount, account_id)
            if account is None or account.encrypted_token_reference is None:
                raise NoConnectedAccount(f"account {account_id} missing or empty")
            tokens = store.load(account.encrypted_token_reference)
            access, refreshed, was_refreshed = store.valid_access_token(tokens)
            if was_refreshed:
                account.encrypted_token_reference = store.save(refreshed)
                session.commit()
            return access

    return getter


def build_adapter(account: ConnectedAccount) -> ChannelAdapter:
    provider = account.provider
    if provider == "gmail":
        return GmailAdapter(
            token_getter=_token_getter(account.id, "gmail"),
            from_addr=account.provider_account_id,
        )
    if provider == "outlook":
        return OutlookAdapter(token_getter=_token_getter(account.id, "outlook"))
    if provider == "imap_smtp":
        if account.encrypted_token_reference is None:
            raise NoConnectedAccount("imap_smtp account has no stored credentials")
        store = TokenStore("imap_smtp")
        creds = store.load(account.encrypted_token_reference)
        return ImapSmtpAdapter(
            ImapSmtpConfig(
                email=creds["email"],
                smtp_host=creds["smtp_host"],
                imap_host=creds["imap_host"],
                username=creds["username"],
                password=creds["password"],
                smtp_port=int(creds.get("smtp_port", 587)),
                imap_port=int(creds.get("imap_port", 993)),
                sent_folder=creds.get("sent_folder", "Sent"),
            )
        )
    raise ValueError(f"unknown connected-account provider '{provider}'")


def active_account_for_user(session: Session, user_id) -> ConnectedAccount | None:
    return session.scalars(
        select(ConnectedAccount)
        .where(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.status == "active",
            ConnectedAccount.revoked_at.is_(None),
        )
        .order_by(ConnectedAccount.created_at.desc())
    ).first()


def resolve_outbox_adapter(session: Session, row: OutboxMessage) -> ChannelAdapter:
    """Adapter for delivering one outbox row: the case owner's active account."""
    case = session.get(Case, row.case_id)
    if case is None:
        raise NoConnectedAccount(f"case {row.case_id} not found")
    account = active_account_for_user(session, case.user_id)
    if account is None:
        raise NoConnectedAccount(f"user {case.user_id} has no active email account")
    return build_adapter(account)


def inbound_adapters(session: Session) -> list[ChannelAdapter]:
    """One adapter per active connected account, for inbound polling."""
    accounts = session.scalars(
        select(ConnectedAccount).where(
            ConnectedAccount.status == "active", ConnectedAccount.revoked_at.is_(None)
        )
    ).all()
    return [build_adapter(a) for a in accounts]
