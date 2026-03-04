"""Tests for services.email.encryption — Fernet encryption wrapper."""

import pytest
from cryptography.fernet import Fernet

from services.email.encryption import FernetEncryption


@pytest.fixture
def valid_key():
    return Fernet.generate_key().decode()


class TestFernetEncryption:
    def test_encrypt_decrypt_roundtrip(self, valid_key):
        enc = FernetEncryption(valid_key)
        plaintext = "Hello, world! This is a secret email body."
        ciphertext = enc.encrypt(plaintext)
        assert ciphertext != plaintext
        assert enc.decrypt(ciphertext) == plaintext

    def test_no_key_passthrough(self):
        enc = FernetEncryption(None)
        assert not enc.is_configured
        text = "plain text body"
        assert enc.encrypt(text) == text
        assert enc.decrypt(text) == text

    def test_wrong_key_raises(self, valid_key):
        enc1 = FernetEncryption(valid_key)
        enc2 = FernetEncryption(Fernet.generate_key().decode())
        ciphertext = enc1.encrypt("secret")
        with pytest.raises(ValueError, match="Decryption failed"):
            enc2.decrypt(ciphertext)

    def test_is_configured(self, valid_key):
        assert FernetEncryption(valid_key).is_configured
        assert not FernetEncryption(None).is_configured

    def test_empty_string(self, valid_key):
        enc = FernetEncryption(valid_key)
        ciphertext = enc.encrypt("")
        assert enc.decrypt(ciphertext) == ""

    def test_unicode_handling(self, valid_key):
        enc = FernetEncryption(valid_key)
        text = "日本語テスト 🔒 émojis"
        ciphertext = enc.encrypt(text)
        assert enc.decrypt(ciphertext) == text
