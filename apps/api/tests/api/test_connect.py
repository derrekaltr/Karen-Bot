"""Connected-accounts endpoints: IMAP connect, listing, revocation, and the
OAuth callback with a faked token exchange."""

import httpx
import pytest


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module

    return TestClient(main_module.app)


HEADERS = {"X-User-Email": "dana@example.com"}


def _seed(http):
    http.post("/dev/seed")


def test_imap_connect_list_revoke(client):
    _seed(client)
    r = client.post(
        "/connect/imap_smtp",
        headers=HEADERS,
        json={
            "email": "dana@fastmail.example",
            "smtp_host": "smtp.fastmail.example",
            "imap_host": "imap.fastmail.example",
            "username": "dana@fastmail.example",
            "password": "app-password",
        },
    )
    assert r.status_code == 200, r.text
    account_id = r.json()["id"]
    assert r.json()["provider"] == "imap_smtp"

    accounts = client.get("/connect/accounts", headers=HEADERS).json()
    assert len(accounts) == 1 and accounts[0]["status"] == "active"

    # Credentials are stored encrypted, never in plaintext.
    from sqlalchemy import select

    from karenbot.db.session import get_session_factory
    from karenbot.domain.models import ConnectedAccount
    from karenbot.security.crypto import decrypt_json

    with get_session_factory()() as session:
        row = session.scalars(select(ConnectedAccount)).one()
        assert "app-password" not in (row.encrypted_token_reference or "")
        assert decrypt_json(row.encrypted_token_reference)["password"] == "app-password"

    r = client.post(f"/connect/accounts/{account_id}/revoke", headers=HEADERS)
    assert r.json()["status"] == "revoked"
    with get_session_factory()() as session:
        row = session.scalars(select(ConnectedAccount)).one()
        assert row.encrypted_token_reference is None  # credentials dropped


def test_oauth_start_requires_configured_client(client, monkeypatch):
    _seed(client)
    monkeypatch.delenv("KARENBOT_GOOGLE_CLIENT_ID", raising=False)
    from karenbot.config import get_settings

    get_settings.cache_clear()
    r = client.get("/connect/gmail/start", headers=HEADERS)
    assert r.status_code == 503
    get_settings.cache_clear()


def test_oauth_callback_stores_encrypted_tokens(db, monkeypatch):
    """Full callback path with a faked Google token exchange + userinfo."""
    monkeypatch.setenv("KARENBOT_GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("KARENBOT_GOOGLE_CLIENT_SECRET", "cs")
    from karenbot.config import get_settings

    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "access_token": "at-123",
                    "refresh_token": "rt-456",
                    "expires_in": 3599,
                    "token_type": "Bearer",
                },
            )
        if "userinfo" in request.url.path:
            return httpx.Response(200, json={"email": "dana@gmail.example"})
        return httpx.Response(404)

    from fastapi.testclient import TestClient

    import karenbot.api.main as main_module
    from karenbot.api import connect

    # Rebuild the connect router with the mocked HTTP client.
    app = main_module.app
    test_router = connect.build_router(
        http=httpx.Client(transport=httpx.MockTransport(handler))
    )
    app.include_router(test_router, prefix="/connect-test")

    client = TestClient(app)
    client.post("/dev/seed")

    from karenbot.db.session import get_session_factory as _gsf
    from karenbot.domain.models import User as _User

    with _gsf()() as session:
        from sqlalchemy import select as _select

        dana_id = session.scalars(
            _select(_User.id).where(_User.email == "dana@example.com")
        ).one()

    # Forged/garbage state is rejected.
    r = client.get("/connect-test/gmail/callback?code=auth-code&state=forged")
    assert r.status_code == 400

    # Wrong-provider state is rejected.
    wrong = connect.make_oauth_state(dana_id, "outlook")
    r = client.get(f"/connect-test/gmail/callback?code=auth-code&state={wrong}")
    assert r.status_code == 400

    state = connect.make_oauth_state(dana_id, "gmail")
    r = client.get(f"/connect-test/gmail/callback?code=auth-code&state={state}")
    assert r.status_code == 200, r.text
    assert r.json()["connected"] == "dana@gmail.example"

    from sqlalchemy import select

    from karenbot.db.session import get_session_factory
    from karenbot.domain.models import ConnectedAccount
    from karenbot.security.crypto import decrypt_json

    with get_session_factory()() as session:
        row = session.scalars(
            select(ConnectedAccount).where(ConnectedAccount.provider == "gmail")
        ).one()
        tokens = decrypt_json(row.encrypted_token_reference)
        assert tokens["access_token"] == "at-123"
        assert tokens["refresh_token"] == "rt-456"
        assert row.provider_account_id == "dana@gmail.example"
    get_settings.cache_clear()
