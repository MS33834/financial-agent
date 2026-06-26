"""字段级加密工具.

使用 Fernet 对称加密保护数据库中的敏感字段。
密钥从应用的 SECRET_KEY 通过 PBKDF2 派生，避免直接使用短密钥。
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import JSON, Text, TypeDecorator

from app.config import get_settings


class EncryptionError(Exception):
    """加密/解密异常."""

    pass


def _derive_key(secret: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """从 SECRET_KEY 派生 Fernet 密钥.

    Args:
        secret: 应用主密钥。
        salt: 可选盐值；未提供则生成随机盐值。

    Returns:
        (fernet_key, salt) 元组。
    """
    if salt is None:
        salt = Fernet.generate_key()[:16]
    key = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, iterations=100_000, dklen=32)
    fernet_key = base64.urlsafe_b64encode(key)
    return fernet_key, salt


def _get_fernet(salt: bytes | None = None) -> Fernet:
    """获取 Fernet 实例."""
    settings = get_settings()
    secret = settings.secret_key
    if not secret:
        raise EncryptionError("SECRET_KEY is not configured")
    fernet_key, _ = _derive_key(secret, salt)
    return Fernet(fernet_key)


def _get_fernet_with_secret(secret: str, salt: bytes) -> Fernet:
    """使用指定 secret 与 salt 派生 Fernet 实例（用于密钥轮换）."""
    fernet_key, _ = _derive_key(secret, salt)
    return Fernet(fernet_key)


def get_key_version() -> str:
    """返回当前密钥版本（基于 SECRET_KEY 的哈希前 8 位）.

    用于密文版本前缀，便于密钥轮换时识别需要重新加密的记录。
    """
    settings = get_settings()
    secret = settings.secret_key
    return hashlib.sha256(secret.encode()).hexdigest()[:8]


def _is_version_prefix(s: str) -> bool:
    """检查是否为密钥版本前缀（v + 8 位十六进制）."""
    return (
        len(s) == 9
        and s[0] == "v"
        and all(c in "0123456789abcdef" for c in s[1:])
    )


def _parse_ciphertext(ciphertext: str) -> tuple[str | None, bytes, bytes]:
    """解析密文，返回 (版本, salt, 加密数据).

    新格式: ``v{version}:salt:ciphertext``
    旧格式: ``salt:ciphertext``（版本为 None，按 v0 处理）

    Args:
        ciphertext: 密文字符串。

    Returns:
        (版本字符串或 None, salt 字节, 加密数据字节)。

    Raises:
        EncryptionError: 密文格式不合法时抛出。
    """
    parts = ciphertext.split(":", 2)
    if len(parts) == 3 and _is_version_prefix(parts[0]):
        version: str | None = parts[0]
        encoded_salt = parts[1]
        encoded_cipher = parts[2]
    elif len(parts) == 2:
        version = None
        encoded_salt = parts[0]
        encoded_cipher = parts[1]
    else:
        raise EncryptionError("Invalid ciphertext format")

    try:
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
        encrypted_data = base64.urlsafe_b64decode(encoded_cipher.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise EncryptionError("Invalid ciphertext encoding") from exc

    return version, salt, encrypted_data


class FieldEncryption:
    """字段加密器.

    对字符串或 JSON 可序列化对象进行加密/解密。
    密文格式：``v{version}:salt:ciphertext``（盐值使用 base64 编码）。
    旧格式 ``salt:ciphertext`` 在解密时自动识别为 v0。
    """

    _SEP = ":"

    @classmethod
    def encrypt(cls, value: Any) -> str:
        """加密值.

        Args:
            value: 字符串或可 JSON 序列化的对象。

        Returns:
            形如 ``v{version}:salt:ciphertext`` 的密文字符串。
        """
        if value is None:
            raise EncryptionError("Cannot encrypt None")

        if isinstance(value, str):
            plaintext = value.encode("utf-8")
        else:
            plaintext = json.dumps(value, ensure_ascii=False).encode("utf-8")

        salt = Fernet.generate_key()[:16]
        fernet = _get_fernet(salt)
        ciphertext = fernet.encrypt(plaintext)
        encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii")
        encoded_cipher = base64.urlsafe_b64encode(ciphertext).decode("ascii")
        # 附加密钥版本前缀，便于密钥轮换时识别需要重新加密的记录
        version = get_key_version()
        return f"v{version}{cls._SEP}{encoded_salt}{cls._SEP}{encoded_cipher}"

    @classmethod
    def decrypt(cls, ciphertext: str) -> Any:
        """解密密文.

        兼容新格式 ``v{version}:salt:ciphertext`` 与旧格式 ``salt:ciphertext``
        （旧格式自动识别为 v0）。

        Args:
            ciphertext: 密文字符串。

        Returns:
            原始字符串或 JSON 反序列化后的对象。
        """
        if not isinstance(ciphertext, str):
            raise EncryptionError("Ciphertext must be a string")

        _version, salt, encrypted_data = _parse_ciphertext(ciphertext)
        fernet = _get_fernet(salt)
        try:
            plaintext = fernet.decrypt(encrypted_data)
        except InvalidToken as exc:
            raise EncryptionError("Failed to decrypt field") from exc

        text = plaintext.decode("utf-8")
        # 尝试按 JSON 解析，失败则返回原始字符串
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


def _decrypt_with_secret(ciphertext: str, secret: str) -> Any:
    """使用指定 secret 解密密文（用于密钥轮换场景）.

    Args:
        ciphertext: 密文字符串。
        secret: 用于解密的密钥。

    Returns:
        原始字符串或 JSON 反序列化后的对象。
    """
    _version, salt, encrypted_data = _parse_ciphertext(ciphertext)
    fernet = _get_fernet_with_secret(secret, salt)
    try:
        plaintext = fernet.decrypt(encrypted_data)
    except InvalidToken as exc:
        raise EncryptionError("Failed to decrypt field with provided key") from exc

    text = plaintext.decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def re_encrypt(value: str, old_key: str) -> str:
    """用旧密钥解密后用当前密钥重新加密.

    用于密钥轮换场景：将使用旧 SECRET_KEY 加密的密文，
    解密后用当前 SECRET_KEY 重新加密并附加新的版本前缀。

    Args:
        value: 待重新加密的密文。
        old_key: 旧的 SECRET_KEY。

    Returns:
        用当前密钥重新加密后的密文（带新版本前缀）。
    """
    plaintext = _decrypt_with_secret(value, old_key)
    return FieldEncryption.encrypt(plaintext)


class EncryptedJSON(TypeDecorator[dict[str, Any] | None]):
    """SQLAlchemy 加密 JSON 类型.

    写入数据库前加密，读取后自动解密。
    """

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any | None, _dialect: Any) -> Any | None:
        if value is None:
            return None
        return FieldEncryption.encrypt(value)

    def process_result_value(self, value: Any | None, _dialect: Any) -> Any | None:
        if value is None:
            return None
        return FieldEncryption.decrypt(value)


class EncryptedString(TypeDecorator[str | None]):
    """SQLAlchemy 加密字符串类型.

    写入数据库前加密，读取后自动解密。
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any | None, _dialect: Any) -> Any | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise EncryptionError("EncryptedString only accepts string values")
        return FieldEncryption.encrypt(value)

    def process_result_value(self, value: Any | None, _dialect: Any) -> Any | None:
        if value is None:
            return None
        decrypted = FieldEncryption.decrypt(value)
        if not isinstance(decrypted, str):
            raise EncryptionError("EncryptedString decrypted value is not a string")
        return decrypted
