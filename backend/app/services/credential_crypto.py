"""Encryption/decryption for platform credentials stored in the DB.

Key derivation: HKDF-SHA256 from SECRET_KEY, unique per (user_id, platform).
This means a single compromised key only exposes one user's one platform.
"""
import base64
import json

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings


def _derive_fernet(user_id: str, platform: str) -> Fernet:
    """Derive a per-(user, platform) Fernet key from the app secret."""
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        # salt encodes who this key belongs to
        salt=(user_id + ":" + platform).encode(),
        info=b"platform-credentials-v1",
    )
    raw_key = kdf.derive(settings.secret_key.encode())
    return Fernet(base64.urlsafe_b64encode(raw_key))


def encrypt(plaintext: str, user_id: str, platform: str) -> str:
    """Return a Fernet token (str) for *plaintext*."""
    f = _derive_fernet(user_id, platform)
    return f.encrypt(plaintext.encode()).decode()


def decrypt(token: str, user_id: str, platform: str) -> str:
    """Recover plaintext from a Fernet *token*."""
    f = _derive_fernet(user_id, platform)
    return f.decrypt(token.encode()).decode()


def encrypt_cookies(cookies: dict, user_id: str, platform: str) -> str:
    return encrypt(json.dumps(cookies), user_id, platform)


def decrypt_cookies(token: str, user_id: str, platform: str) -> dict:
    return json.loads(decrypt(token, user_id, platform))
