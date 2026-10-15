"""Connected-accounts API: OAuth connect flows (Gmail, Outlook) and
credential-based IMAP/SMTP setup.

CSRF protection: the OAuth `state` is a Fernet-encrypted payload bound to the
authenticated user id with a short expiry and a random nonce. The callback
decrypts and validates it; a forged or replayed-after-expiry state is
rejected.
"""

import secrets
import time
import uuid
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.channels import oauth
from karenbot.domain.models import ConnectedAccount, User, utcnow
from karenbot.security.crypto import decrypt_json, encrypt_json

STATE_TTL_SECONDS = 600


def make_oauth_state(user_id: uuid.UUID, provider: str) -> str:
    return encrypt_json(
        {
            "user_id": str(user_id),
            "provider": provider,
            "nonce": secrets.token_urlsafe(16),
            "exp": time.time() + STATE_TTL_SECONDS,
        }
    )


def parse_oauth_state(state: str, provider: str) -> uuid.UUID:
    try:
        payload = decrypt_json(state)
    except Exception as exc:
        raise HTTPException(400, "invalid oauth state") from exc
    if payload.get("provider") != provider:
        raise HTTPException(400, "oauth state provider mismatch")
    if time.time() > float(payload.get("exp", 0)):
        raise HTTPException(400, "oauth state expired — restart the connect flow")
    return uuid.UUID(payload["user_id"])


class ConnectedAccountOut(BaseModel):
    id: uuid.UUID
    provider: str
    provider_account_id: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


def _upsert_account(
    db: Session, user: User, provider: str, email_addr: str, tokens: dict[str, Any], scopes: list[str]
) -> ConnectedAccount:
    account = db.scalars(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user.id,
            ConnectedAccount.provider == provider,
            ConnectedAccount.provider_account_id == email_addr,
        )
    ).first()
    if account is None:
        account = ConnectedAccount(
            user_id=user.id, provider=provider, provider_account_id=email_addr
        )
        db.add(account)
    account.encrypted_token_reference = encrypt_json(tokens)
    account.granted_scopes = scopes
    account.status = "active"
    account.revoked_at = None
    db.flush()
    return account


def _fetch_profile_email(provider: str, access_token: str, http: httpx.Client) -> str:
    headers = {"Authorization": f"Bearer {access_token}"}
    if provider == "gmail":
        response = http.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers)
        response.raise_for_status()
        return response.json()["email"]
    if provider == "outlook":
        response = http.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("mail") or data["userPrincipalName"]
    raise ValueError(provider)


def build_router(http: httpx.Client | None = None) -> APIRouter:
    from karenbot.api.main import current_user, get_db

    client = http or httpx.Client(timeout=30)
    r = APIRouter()

    @r.get("/accounts", response_model=list[ConnectedAccountOut])
    def list_accounts(
        user: User = Depends(current_user), db: Session = Depends(get_db)
    ) -> list[ConnectedAccount]:
        return list(
            db.scalars(
                select(ConnectedAccount)
                .where(ConnectedAccount.user_id == user.id)
                .order_by(ConnectedAccount.created_at.desc())
            )
        )

    @r.post("/accounts/{account_id}/revoke")
    def revoke_account(
        account_id: uuid.UUID,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> dict:
        account = db.get(ConnectedAccount, account_id)
        if account is None or account.user_id != user.id:
            raise HTTPException(404, "account not found")
        account.status = "revoked"
        account.revoked_at = utcnow()
        account.encrypted_token_reference = None  # drop credentials immediately
        return {"status": "revoked"}

    @r.get("/{provider}/start")
    def start(
        provider: str, user: User = Depends(current_user)
    ) -> dict:
        if provider not in oauth.PROVIDERS:
            raise HTTPException(404, f"unknown provider '{provider}'")
        state = make_oauth_state(user.id, provider)
        try:
            return {
                "auth_url": oauth.build_auth_url(provider, state, login_hint=user.email)
            }
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

    @r.get("/{provider}/callback")
    def callback(provider: str, code: str, state: str, db: Session = Depends(get_db)) -> dict:
        if provider not in oauth.PROVIDERS:
            raise HTTPException(404, f"unknown provider '{provider}'")
        user_id = parse_oauth_state(state, provider)
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(400, "unknown state")
        tokens = oauth.exchange_code(provider, code, client)
        address = _fetch_profile_email(provider, tokens["access_token"], client)
        tokens["email"] = address
        account = _upsert_account(
            db, user, provider, address, tokens, oauth.PROVIDERS[provider].scopes
        )
        return {"connected": address, "provider": provider, "account_id": str(account.id)}

    class ImapSmtpIn(BaseModel):
        email: str
        smtp_host: str
        imap_host: str
        username: str
        password: str
        smtp_port: int = 587
        imap_port: int = 993
        sent_folder: str = "Sent"

    @r.post("/imap_smtp", response_model=ConnectedAccountOut)
    def connect_imap(
        payload: ImapSmtpIn,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> ConnectedAccount:
        return _upsert_account(
            db,
            user,
            "imap_smtp",
            payload.email,
            payload.model_dump(),
            ["imap", "smtp"],
        )

    return r
