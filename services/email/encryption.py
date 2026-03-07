"""Fernet symmetric encryption for email body at rest."""

import logging

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class FernetEncryption:
    """Encrypt / decrypt strings using Fernet (AES-128-CBC + HMAC-SHA256).

    If no key is provided, operates in passthrough mode (dev only) with a
    critical warning logged on first use.
    """

    def __init__(self, key: str | None):
        self._fernet: Fernet | None = None
        if key:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        else:
            logger.critical(
                "EMAIL_ENCRYPTION_KEY not set — email bodies stored in PLAINTEXT. "
                "Set this in production!"
            )

    @property
    def is_configured(self) -> bool:
        return self._fernet is not None

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext and return base64 ciphertext string."""
        if not self._fernet:
            return plaintext
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext back to plaintext string."""
        if not self._fernet:
            return ciphertext
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, Exception) as exc:
            raise ValueError("Decryption failed") from exc
