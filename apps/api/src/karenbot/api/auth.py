"""Authentication: Clerk session JWTs, with a dev-mode header fallback.

Production path: the web app sends `Authorization: Bearer <Clerk session
token>`; we verify it against Clerk's JWKS (RS256, cached keys) and
auto-provision our `users` row from the token's claims on first sight.

Dev path (dev_mode + allow_dev_auth only): the `X-User-Email` header keeps
local development, tests, and the demo working without Clerk credentials.
"""

import base64
import logging
from functools import lru_cache

import httpx
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from karenbot.config import get_settings
from karenbot.domain.models import User

logger = logging.getLogger(__name__)


def frontend_api_from_publishable_key(publishable_key: str) -> str:
    """Clerk publishable keys are `pk_(test|live)_<base64("<domain>$")>`."""
    try:
        encoded = publishable_key.split("_", 2)[2]
        padded = encoded + "=" * (-len(encoded) % 4)
        domain = base64.b64decode(padded).decode().rstrip("$")
        return f"https://{domain}"
    except Exception as exc:  # pragma: no cover - malformed key
        raise RuntimeError("invalid Clerk publishable key") from exc


def jwks_url() -> str:
    settings = get_settings()
    if settings.clerk_jwks_url:
        return settings.clerk_jwks_url
    if settings.clerk_publishable_key:
        return f"{frontend_api_from_publishable_key(settings.clerk_publishable_key)}/.well-known/jwks.json"
    raise RuntimeError("Clerk is not configured (no publishable key or JWKS URL)")


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url(), cache_keys=True, lifespan=3600)


def reset_jwks_cache() -> None:
    _jwks_client.cache_clear()


def verify_session_token(token: str) -> dict:
    """Validate a Clerk session JWT and return its claims."""
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},  # Clerk session tokens carry azp, not aud
            leeway=10,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"invalid session token: {exc}") from exc


def _provision_user(db: Session, claims: dict) -> User:
    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        raise HTTPException(401, "session token missing subject")
    user = db.scalars(select(User).where(User.clerk_user_id == clerk_user_id)).first()
    if user is not None:
        return user
    # Clerk session tokens include email when the instance is configured to;
    # fall back to a stable placeholder keyed by the Clerk id.
    email = claims.get("email") or f"{clerk_user_id}@users.clerk.local"
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is not None:
        user.clerk_user_id = clerk_user_id
        return user
    user = User(
        email=email,
        display_name=claims.get("name") or claims.get("first_name"),
        clerk_user_id=clerk_user_id,
    )
    db.add(user)
    db.flush()
    logger.info("provisioned user %s from Clerk identity", user.id)
    return user


def current_user_factory(get_db):
    """Builds the FastAPI dependency (avoids a circular import with main)."""

    def current_user(
        authorization: str | None = Header(default=None),
        x_user_email: str | None = Header(default=None),
        db: Session = Depends(get_db),
    ) -> User:
        settings = get_settings()
        if authorization and authorization.lower().startswith("bearer "):
            claims = verify_session_token(authorization.split(" ", 1)[1])
            return _provision_user(db, claims)
        if settings.dev_mode and settings.allow_dev_auth and x_user_email:
            user = db.scalars(select(User).where(User.email == x_user_email)).first()
            if user is None:
                raise HTTPException(401, "unknown user — call POST /dev/seed first")
            return user
        raise HTTPException(401, "authentication required")

    return current_user


def fetch_clerk_email(clerk_user_id: str) -> str | None:
    """Backfill: ask Clerk's backend API for the user's primary email."""
    settings = get_settings()
    if not settings.clerk_secret_key:
        return None
    response = httpx.get(
        f"https://api.clerk.com/v1/users/{clerk_user_id}",
        headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
        timeout=10,
    )
    if response.status_code != 200:
        return None
    data = response.json()
    primary_id = data.get("primary_email_address_id")
    for item in data.get("email_addresses", []):
        if item.get("id") == primary_id:
            return item.get("email_address")
    return None
