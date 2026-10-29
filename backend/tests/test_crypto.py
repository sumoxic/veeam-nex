"""凭据加密：往返、前缀与密钥不匹配。"""
import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.security.crypto import CIPHER_PREFIX, DecryptionError, decrypt, encrypt


def test_encrypt_decrypt_roundtrip():
    ciphertext = encrypt("Admin@12345")
    assert ciphertext.startswith(CIPHER_PREFIX)
    assert ciphertext != "Admin@12345"
    assert decrypt(ciphertext) == "Admin@12345"


def test_encrypt_is_randomized():
    assert encrypt("same-secret") != encrypt("same-secret")


def test_decrypt_empty_or_bad_format():
    with pytest.raises(DecryptionError):
        decrypt("")
    with pytest.raises(DecryptionError):
        decrypt("plain-text")


def test_decrypt_with_other_key_fails(monkeypatch):
    ciphertext = encrypt("top-secret")
    other = Fernet.generate_key().decode("ascii")

    class _Settings:
        secret_key = other
        previous_secret_key_list: list[str] = []

    monkeypatch.setattr("app.security.crypto.get_settings", lambda: _Settings())
    with pytest.raises(DecryptionError):
        decrypt(ciphertext)
