import time

import httpx
import pytest


def _clear_settings():
    from karenbot.config import get_settings

    get_settings.cache_clear()


def test_token_crypto_roundtrip(monkeypatch):
    monkeypatch.setenv("KARENBOT_DEV_MODE", "true")
    _clear_settings()
    from karenbot.security.crypto import decrypt_json, encrypt_json

    payload = {"access_token": "abc", "refresh_token": "r", "expires_at": 123.0}
    assert decrypt_json(encrypt_json(payload)) == payload
    _clear_settings()


def test_production_requires_explicit_key(monkeypatch):
    monkeypatch.setenv("KARENBOT_DEV_MODE", "false")
    monkeypatch.delenv("KARENBOT_TOKEN_ENCRYPTION_KEY", raising=False)
    _clear_settings()
    from karenbot.security.crypto import get_fernet

    with pytest.raises(RuntimeError, match="TOKEN_ENCRYPTION_KEY"):
        get_fernet()
    _clear_settings()


def test_auth_url_contains_required_params(monkeypatch):
    monkeypatch.setenv("KARENBOT_GOOGLE_CLIENT_ID", "client-123")
    monkeypatch.setenv("KARENBOT_GOOGLE_CLIENT_SECRET", "secret")
    _clear_settings()
    from karenbot.channels.oauth import build_auth_url

    url = build_auth_url("gmail", state="st4te")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=client-123" in url
    assert "gmail.send" in url and "gmail.readonly" in url
    assert "state=st4te" in url
    assert "access_type=offline" in url
    _clear_settings()


def test_unconfigured_provider_refuses(monkeypatch):
    monkeypatch.delenv("KARENBOT_MICROSOFT_CLIENT_ID", raising=False)
    _clear_settings()
    from karenbot.channels.oauth import build_auth_url

    with pytest.raises(RuntimeError, match="not configured"):
        build_auth_url("outlook", state="x")
    _clear_settings()


def _mock_http(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_token_store_refreshes_expired_token(monkeypatch):
    monkeypatch.setenv("KARENBOT_GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("KARENBOT_GOOGLE_CLIENT_SECRET", "cs")
    _clear_settings()
    from karenbot.channels.oauth import TokenStore

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert "refresh_token" in request.read().decode()
        return httpx.Response(
            200, json={"access_token": "new-token", "expires_in": 3600, "token_type": "Bearer"}
        )

    store = TokenStore("gmail", http=_mock_http(handler))
    expired = {"access_token": "old", "refresh_token": "keep-me", "expires_at": time.time() - 10}
    access, refreshed, was_refreshed = store.valid_access_token(expired)
    assert was_refreshed and access == "new-token"
    assert refreshed["refresh_token"] == "keep-me"  # preserved across refresh

    fresh = {"access_token": "still-good", "refresh_token": "r", "expires_at": time.time() + 3600}
    access2, _, was_refreshed2 = store.valid_access_token(fresh)
    assert not was_refreshed2 and access2 == "still-good"
    assert len(calls) == 1
    _clear_settings()
