"""OAuth flows and token lifecycle for email providers.

Tokens are stored Fernet-encrypted on connected_accounts (see
security/crypto.py) as:
    {access_token, refresh_token, expires_at (epoch), token_type, scope,
     email, extra: {...}}

Gmail scopes are Google *restricted* scopes: production use requires
verification + CASA assessment; until then the OAuth client runs in testing
mode with allowlisted users (docs/legal-risk.md §Google).
"""

import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

from karenbot.config import get_settings
from karenbot.security.crypto import decrypt_json, encrypt_json

REFRESH_SKEW_SECONDS = 120


@dataclass(frozen=True)
class OAuthProvider:
    key: str
    auth_url: str
    token_url: str
    scopes: list[str]

    def client(self) -> tuple[str, str]:
        settings = get_settings()
        if self.key == "gmail":
            return settings.google_client_id, settings.google_client_secret
        if self.key == "outlook":
            return settings.microsoft_client_id, settings.microsoft_client_secret
        raise ValueError(f"no oauth client for provider {self.key}")


PROVIDERS: dict[str, OAuthProvider] = {
    "gmail": OAuthProvider(
        key="gmail",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=[
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
            "openid",
            "email",
        ],
    ),
    "outlook": OAuthProvider(
        key="outlook",
        auth_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        scopes=[
            "offline_access",
            "https://graph.microsoft.com/Mail.Send",
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/User.Read",
        ],
    ),
}


def redirect_uri(provider_key: str) -> str:
    return f"{get_settings().oauth_redirect_base}/connect/{provider_key}/callback"


def build_auth_url(provider_key: str, state: str) -> str:
    provider = PROVIDERS[provider_key]
    client_id, _ = provider.client()
    if not client_id:
        raise RuntimeError(f"{provider_key} OAuth client is not configured")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri(provider_key),
        "response_type": "code",
        "scope": " ".join(provider.scopes),
        "state": state,
        "access_type": "offline",  # Google: request a refresh token
        "prompt": "consent",
    }
    return f"{provider.auth_url}?{urllib.parse.urlencode(params)}"


def _normalize(token_response: dict[str, Any], prior: dict[str, Any] | None = None) -> dict[str, Any]:
    prior = prior or {}
    return {
        "access_token": token_response["access_token"],
        # Providers omit refresh_token on refresh responses; keep the old one.
        "refresh_token": token_response.get("refresh_token") or prior.get("refresh_token"),
        "expires_at": time.time() + float(token_response.get("expires_in", 3600)),
        "token_type": token_response.get("token_type", "Bearer"),
        "scope": token_response.get("scope", prior.get("scope", "")),
        "email": prior.get("email"),
    }


def exchange_code(provider_key: str, code: str, http: httpx.Client) -> dict[str, Any]:
    provider = PROVIDERS[provider_key]
    client_id, client_secret = provider.client()
    response = http.post(
        provider.token_url,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri(provider_key),
        },
    )
    response.raise_for_status()
    return _normalize(response.json())


def refresh_tokens(
    provider_key: str, tokens: dict[str, Any], http: httpx.Client
) -> dict[str, Any]:
    provider = PROVIDERS[provider_key]
    client_id, client_secret = provider.client()
    response = http.post(
        provider.token_url,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": tokens["refresh_token"],
            "grant_type": "refresh_token",
        },
    )
    response.raise_for_status()
    return _normalize(response.json(), prior=tokens)


class TokenStore:
    """Loads, refreshes, and persists a connected account's tokens."""

    def __init__(self, provider_key: str, http: httpx.Client | None = None):
        self.provider_key = provider_key
        self.http = http or httpx.Client(timeout=30)

    def load(self, ciphertext: str) -> dict[str, Any]:
        return decrypt_json(ciphertext)

    def save(self, tokens: dict[str, Any]) -> str:
        return encrypt_json(tokens)

    def valid_access_token(self, tokens: dict[str, Any]) -> tuple[str, dict[str, Any], bool]:
        """Returns (access_token, possibly-refreshed tokens, was_refreshed)."""
        if time.time() < tokens.get("expires_at", 0) - REFRESH_SKEW_SECONDS:
            return tokens["access_token"], tokens, False
        refreshed = refresh_tokens(self.provider_key, tokens, self.http)
        return refreshed["access_token"], refreshed, True
