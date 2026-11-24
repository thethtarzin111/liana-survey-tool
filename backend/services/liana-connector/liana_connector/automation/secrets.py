"""Encrypts the client secret before it is stored (Fernet: AES with an integrity check).

The key comes from INTEGRATION_SECRET_KEY. Changing it makes saved secrets unreadable:
the page then asks for the secret again."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class UnreadableSecret(Exception):
    """The saved secret was encrypted with another key."""


def _fernet(key: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def encrypt(secret: str, key: str) -> bytes:
    return _fernet(key).encrypt(secret.encode())


def decrypt(token: bytes, key: str) -> str:
    try:
        return _fernet(key).decrypt(bytes(token)).decode()
    except InvalidToken as error:
        raise UnreadableSecret from error
