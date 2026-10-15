"""Clerk session-JWT verification with a locally signed token + stub JWKS."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from karenbot.api import auth


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture
def stub_jwks(rsa_keypair, monkeypatch):
    _, public_key = rsa_keypair

    class StubSigningKey:
        key = public_key

    class StubClient:
        def get_signing_key_from_jwt(self, token):
            return StubSigningKey()

    monkeypatch.setattr(auth, "_jwks_client", lambda: StubClient())


def _token(private_key, **overrides) -> str:
    claims = {
        "sub": "user_clerk123",
        "email": "derrek@example.com",
        "name": "Derrek",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256")


def test_valid_token_verifies_and_provisions_user(rsa_keypair, stub_jwks, db):
    private_key, _ = rsa_keypair
    claims = auth.verify_session_token(_token(private_key))
    assert claims["sub"] == "user_clerk123"

    with db() as session:
        user = auth._provision_user(session, claims)
        assert user.clerk_user_id == "user_clerk123"
        assert user.email == "derrek@example.com"
        # Second call returns the same row, no duplicate.
        again = auth._provision_user(session, claims)
        assert again.id == user.id


def test_expired_token_rejected(rsa_keypair, stub_jwks):
    private_key, _ = rsa_keypair
    with pytest.raises(HTTPException) as excinfo:
        auth.verify_session_token(_token(private_key, exp=int(time.time()) - 120))
    assert excinfo.value.status_code == 401


def test_tampered_token_rejected(rsa_keypair, stub_jwks):
    private_key, _ = rsa_keypair
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode({"sub": "attacker", "exp": int(time.time()) + 60}, other_key, algorithm="RS256")
    with pytest.raises(HTTPException):
        auth.verify_session_token(forged)


def test_publishable_key_domain_derivation():
    import base64

    encoded = base64.b64encode(b"example-app.clerk.accounts.dev$").decode()
    url = auth.frontend_api_from_publishable_key(f"pk_test_{encoded}")
    assert url == "https://example-app.clerk.accounts.dev"


def test_dev_header_fallback_disabled_outside_dev_mode(db, monkeypatch):
    monkeypatch.setenv("KARENBOT_DEV_MODE", "false")
    from karenbot.config import get_settings

    get_settings.cache_clear()
    try:
        dep = auth.current_user_factory(lambda: None)
        with pytest.raises(HTTPException) as excinfo:
            dep(authorization=None, x_user_email="dana@example.com", db=None)
        assert excinfo.value.status_code == 401
    finally:
        get_settings.cache_clear()
