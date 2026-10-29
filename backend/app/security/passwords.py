"""平台用户口令哈希。

使用 bcrypt。bcrypt 只处理前 72 字节，超长口令需要显式截断，
否则 bcrypt 4.1+ 会直接抛异常。
"""
import bcrypt
from typing import Optional

#: bcrypt 的最大输入长度
BCRYPT_MAX_BYTES = 72
#: 计算代价
BCRYPT_ROUNDS = 12


def _prepare(password: str) -> bytes:
    """把口令转成 bcrypt 可接受的字节串（截断到 72 字节）。"""
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        raw = raw[:BCRYPT_MAX_BYTES]
    return raw


def hash_password(password: str) -> str:
    """计算口令哈希。"""
    if not password:
        raise ValueError("口令不能为空")
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """校验口令是否匹配。"""
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def password_strength_error(password: str) -> Optional[str]:
    """检查口令复杂度，返回错误描述；通过则返回 None。"""
    if len(password) < 8:
        return "口令长度至少 8 位"
    if not any(c.isalpha() for c in password):
        return "口令必须包含字母"
    if not any(c.isdigit() for c in password):
        return "口令必须包含数字"
    return None
