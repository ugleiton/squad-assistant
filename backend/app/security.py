import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


def generate_webhook_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str | None, token_hash: str | None) -> bool:
    if not token or not token_hash:
        return False
    return hmac.compare_digest(hash_token(token), token_hash)


def _fernet() -> Fernet | None:
    key = get_settings().secret_key
    return Fernet(key.encode()) if key else None


def encrypt(value: str | None) -> str | None:
    """Encrypt a secret for storage. Without SQUAD_SECRET_KEY values are stored as-is (dev only)."""
    if value is None:
        return None
    f = _fernet()
    return f"enc:{f.encrypt(value.encode()).decode()}" if f else value


def decrypt(value: str | None) -> str | None:
    if value is None or not value.startswith("enc:"):
        return value
    f = _fernet()
    if f is None:
        raise RuntimeError("SQUAD_SECRET_KEY is required to read encrypted secrets")
    try:
        return f.decrypt(value[4:].encode()).decode()
    except InvalidToken as exc:  # pragma: no cover
        raise RuntimeError("Could not decrypt secret: wrong SQUAD_SECRET_KEY?") from exc
