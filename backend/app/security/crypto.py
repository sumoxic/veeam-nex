"""凭据加密。

使用 Fernet（AES-128-CBC + HMAC-SHA256）对称加密。
密钥只存在于环境变量（backend/.env），不入库、不下发前端、不写进 systemd unit。
密文格式为 "fernet:<token>"，便于将来更换加密方式时平滑迁移。
"""
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

#: 密文前缀，用于标识加密格式
CIPHER_PREFIX = "fernet:"


class DecryptionError(Exception):
    """无法解密（密钥不匹配或数据损坏）。"""


def _fernet(key: str) -> Fernet:
    return Fernet(key.encode() if isinstance(key, str) else key)


def _keys() -> list[str]:
    """当前密钥 + 轮换期间的旧密钥。"""
    settings = get_settings()
    keys = []
    if settings.secret_key:
        keys.append(settings.secret_key)
    keys.extend(settings.previous_secret_key_list)
    if not keys:
        raise DecryptionError(
            "未配置 SECRET_KEY，无法加解密凭据；请执行 scripts/generate_keys.py 生成"
        )
    return keys


def encrypt(plaintext: str) -> str:
    """加密明文，返回 "fernet:<token>"。"""
    if plaintext is None:
        raise ValueError("待加密内容不能为 None")
    token = _fernet(_keys()[0]).encrypt(plaintext.encode("utf-8")).decode("ascii")
    return CIPHER_PREFIX + token


def decrypt(ciphertext: str) -> str:
    """解密 "fernet:<token>"；依次尝试当前密钥与历史密钥。"""
    if not ciphertext:
        raise DecryptionError("密文为空")
    if not ciphertext.startswith(CIPHER_PREFIX):
        raise DecryptionError("密文格式不正确")
    token = ciphertext[len(CIPHER_PREFIX):].encode("ascii")
    last_error: Optional[Exception] = None
    for key in _keys():
        try:
            return _fernet(key).decrypt(token).decode("utf-8")
        except InvalidToken as exc:
            last_error = exc
            continue
    raise DecryptionError(f"解密失败，请检查 SECRET_KEY 是否正确: {last_error}")


def is_encrypted(value: str) -> bool:
    """判断字符串是否为 Fernet 密文。"""
    return bool(value) and value.startswith(CIPHER_PREFIX)
