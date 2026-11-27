"""GitLab webhook credentials: a random token shown once, stored only as a SHA-256 hash."""

import hashlib
import hmac
import secrets


def generate_webhook_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str | None, token_hash: str | None) -> bool:
    if not token or not token_hash:
        return False
    return hmac.compare_digest(hash_token(token), token_hash)
