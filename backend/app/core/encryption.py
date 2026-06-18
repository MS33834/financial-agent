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
from sqlalchemy import JSON, TypeDecorator

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


class FieldEncryption:
    """字段加密器.

    对字符串或 JSON 可序列化对象进行加密/解密。
    密文格式：``salt:ciphertext``（盐值使用 base64 编码）。
    """

    _SEP = ":"

    @classmethod
    def encrypt(cls, value: Any) -> str:
        """加密值.

        Args:
            value: 字符串或可 JSON 序列化的对象。

        Returns:
            形如 ``salt:ciphertext`` 的密文字符串。
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
        return f"{encoded_salt}{cls._SEP}{encoded_cipher}"

    @classmethod
    def decrypt(cls, ciphertext: str) -> Any:
        """解密密文.

        Args:
            ciphertext: ``salt:ciphertext`` 格式的密文。

        Returns:
            原始字符串或 JSON 反序列化后的对象。
        """
        if not isinstance(ciphertext, str):
            raise EncryptionError("Ciphertext must be a string")

        parts = ciphertext.split(cls._SEP, 1)
        if len(parts) != 2:
            raise EncryptionError("Invalid ciphertext format")

        encoded_salt, encoded_cipher = parts
        try:
            salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
            encrypted_data = base64.urlsafe_b64decode(encoded_cipher.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise EncryptionError("Invalid ciphertext encoding") from exc

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
