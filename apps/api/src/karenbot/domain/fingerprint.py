"""Content fingerprinting for duplicate-send detection."""

import hashlib
import re


def message_fingerprint(subject: str | None, body: str) -> str:
    normalized = re.sub(r"\s+", " ", body.strip().lower())
    return hashlib.sha256(f"{subject or ''}:{normalized}".encode()).hexdigest()
