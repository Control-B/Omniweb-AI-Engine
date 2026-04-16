"""Fernet-based encryption for Shopify access tokens stored at rest."""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _derive_key() -> bytes:
    """Derive a 32-byte Fernet key from SECRET_KEY."""
    raw = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(raw)


_fernet = Fernet(_derive_key())


class ShopifyCryptoService:
    """Encrypt / decrypt Shopify access tokens at rest."""

    PREFIX = "enc::"

    @staticmethod
    def encrypt(plaintext: str | None) -> str | None:
        """Encrypt a plaintext token. Returns None if input is None/empty."""
        if not plaintext:
            return None
        if plaintext.startswith(ShopifyCryptoService.PREFIX):
            return plaintext  # already encrypted
        cipher = _fernet.encrypt(plaintext.encode())
        return f"{ShopifyCryptoService.PREFIX}{cipher.decode()}"

    @staticmethod
    def decrypt(ciphertext: str | None) -> str | None:
        """Decrypt a token. Returns None if input is None/empty.
        If the value is NOT encrypted (no prefix), returns it as-is for
        backward compatibility with existing plaintext tokens."""
        if not ciphertext:
            return None
        if not ciphertext.startswith(ShopifyCryptoService.PREFIX):
            return ciphertext  # plaintext (legacy), return as-is
        raw = ciphertext[len(ShopifyCryptoService.PREFIX) :]
        try:
            return _fernet.decrypt(raw.encode()).decode()
        except InvalidToken:
            logger.error("Failed to decrypt Shopify token — invalid key or corrupted ciphertext")
            return None

    @staticmethod
    def is_encrypted(value: str | None) -> bool:
        return bool(value and value.startswith(ShopifyCryptoService.PREFIX))
