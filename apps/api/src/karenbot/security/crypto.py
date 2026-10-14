"""Encryption for OAuth tokens at rest.

`connected_accounts.encrypted_token_reference` stores the Fernet ciphertext
of the provider's token JSON. The key comes from
KARENBOT_TOKEN_ENCRYPTION_KEY (a Fernet key; generate one with
`python -m karenbot.security.crypto`). In dev mode a stable local key is
derived so the stack runs with zero setup; production refuses to start
without an explicit key.
"""

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet

from karenbot.config import get_settings


def _dev_key() -> bytes:
    # Deterministic local-only key. Never acceptable in production.
    return base64.urlsafe_b64encode(hashlib.sha256(b"karenbot-dev-token-key").digest())


def get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.token_encryption_key
    if key:
        return Fernet(key.encode())
    if settings.dev_mode:
        return Fernet(_dev_key())
    raise RuntimeError("KARENBOT_TOKEN_ENCRYPTION_KEY is required outside dev mode")


def encrypt_json(payload: dict[str, Any]) -> str:
    return get_fernet().encrypt(json.dumps(payload).encode()).decode()


def decrypt_json(ciphertext: str) -> dict[str, Any]:
    return json.loads(get_fernet().decrypt(ciphertext.encode()))


if __name__ == "__main__":
    print(Fernet.generate_key().decode())
