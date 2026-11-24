"""Encrypts the client secret before it is stored (Fernet: AES with an integrity check).

The key comes from INTEGRATION_SECRET_KEY. Changing it makes saved secrets unreadable:
the page then asks for the secret again."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

#: The value in config.py and .env.example: public, so only allowed in local development.
DEV_KEY = "change-me-integration-secret-key"
#: The key is hashed into the Fernet key, which is only as strong as a long random value.
MIN_KEY_LENGTH = 32


class UnreadableSecret(Exception):
    """The saved secret was encrypted with another key."""


class WeakKey(RuntimeError):
    """INTEGRATION_SECRET_KEY is the public default or too short outside local development."""


def check_key(key: str, auth_mode: str) -> str:
    """The key, if it may be used. Outside AUTH_MODE=dev it must be set to a long random
    value, so customers' secrets are never encrypted with a key that is in the repo."""
    if auth_mode != "dev" and (key == DEV_KEY or len(key) < MIN_KEY_LENGTH):
        raise WeakKey(
            "Set INTEGRATION_SECRET_KEY to a random value of at least "
            f"{MIN_KEY_LENGTH} characters (for example: openssl rand -base64 48)."
        )
    return key


def _fernet(key: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def encrypt(secret: str, key: str) -> bytes:
    return _fernet(key).encrypt(secret.encode())


def decrypt(token: bytes, key: str) -> str:
    try:
        return _fernet(key).decrypt(bytes(token)).decode()
    except InvalidToken as error:
        raise UnreadableSecret from error
