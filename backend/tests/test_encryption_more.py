"""字段级加密模块（app.core.encryption）补全测试.

覆盖：
- 内部辅助函数：_derive_key / _is_version_prefix / _parse_ciphertext / get_key_version
- FieldEncryption: 加密/解密 None、字符串、对象、错误密文、旧格式兼容
- re_encrypt: 密钥轮换
- EncryptedJSON / EncryptedString SQLAlchemy 类型装饰器
"""

# mypy: disable-error-code="attr-defined"

import base64
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.core.encryption import (
    EncryptedJSON,
    EncryptedString,
    EncryptionError,
    FieldEncryption,
    _derive_key,
    _get_fernet,
    _is_version_prefix,
    _parse_ciphertext,
    get_key_version,
    re_encrypt,
)


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------


def test_derive_key_with_salt() -> None:
    """相同 secret + salt 应派生相同 key."""
    key1, salt1 = _derive_key("secret", salt=b"1234567890123456")
    key2, salt2 = _derive_key("secret", salt=b"1234567890123456")
    assert key1 == key2
    assert salt1 == salt2
    # 应为 base64 编码的 32 字节
    assert len(base64.urlsafe_b64decode(key1)) == 32


def test_derive_key_random_salt() -> None:
    """不传 salt 应返回随机 16 字节 salt，相同 secret 派生不同的 key."""
    key1, salt1 = _derive_key("secret")
    key2, salt2 = _derive_key("secret")
    assert salt1 != salt2
    assert key1 != key2
    assert len(salt1) == 16


def test_is_version_prefix_valid() -> None:
    """符合 v + 8 hex 字符的字符串应识别为版本前缀（小写 hex）."""
    assert _is_version_prefix("v0123abcd") is True
    assert _is_version_prefix("vdeadbeef") is True
    # 函数只接受小写 hex
    assert _is_version_prefix("v0123ABCD") is False


def test_is_version_prefix_invalid() -> None:
    """格式不符应返回 False."""
    assert _is_version_prefix("v0123") is False  # 太短
    assert _is_version_prefix("v0123abcde") is False  # 太长
    assert _is_version_prefix("x0123abcd") is False  # 错前缀
    assert _is_version_prefix("v0123abcg") is False  # 非法 hex
    assert _is_version_prefix("v0123abcd:") is False  # 含分隔符


def test_parse_ciphertext_new_format() -> None:
    """新格式 v{ver}:salt:ciphertext 应被正确解析."""
    salt_b = b"\x00" * 16
    cipher_b = b"\x01" * 32
    encoded = f"vdeadbeef:{base64.urlsafe_b64encode(salt_b).decode()}:{base64.urlsafe_b64encode(cipher_b).decode()}"
    version, salt, cipher = _parse_ciphertext(encoded)
    assert version == "vdeadbeef"
    assert salt == salt_b
    assert cipher == cipher_b


def test_parse_ciphertext_legacy_format() -> None:
    """旧格式 salt:ciphertext 应被识别为 version=None."""
    salt_b = b"\x02" * 16
    cipher_b = b"\x03" * 32
    encoded = f"{base64.urlsafe_b64encode(salt_b).decode()}:{base64.urlsafe_b64encode(cipher_b).decode()}"
    version, salt, cipher = _parse_ciphertext(encoded)
    assert version is None
    assert salt == salt_b
    assert cipher == cipher_b


def test_parse_ciphertext_invalid_format() -> None:
    """格式不合法应抛 EncryptionError."""
    with pytest.raises(EncryptionError):
        _parse_ciphertext("single-segment")
    with pytest.raises(EncryptionError):
        _parse_ciphertext("a:b:c:d")


def test_parse_ciphertext_invalid_encoding() -> None:
    """base64 解码失败应抛 EncryptionError."""
    with pytest.raises(EncryptionError):
        _parse_ciphertext("vdeadbeef:not-base64!@#:alsonotbase64")


def test_get_key_version_consistent() -> None:
    """相同 secret 应返回相同版本哈希."""
    v1 = get_key_version()
    v2 = get_key_version()
    assert v1 == v2
    assert len(v1) == 8


def test_get_key_version_differs_per_secret() -> None:
    """不同 secret 应得到不同版本."""
    with patch("app.core.encryption.get_settings") as mock_settings:
        mock_settings.return_value.secret_key = "secret-a"
        v_a = get_key_version()
        mock_settings.return_value.secret_key = "secret-b"
        v_b = get_key_version()
    assert v_a != v_b


def test_get_fernet_raises_when_secret_missing() -> None:
    """SECRET_KEY 为空时应抛 EncryptionError."""
    with patch("app.core.encryption.get_settings") as mock_settings:
        mock_settings.return_value.secret_key = ""
        with pytest.raises(EncryptionError):
            _get_fernet()


# ------------------------------------------------------------------
# FieldEncryption.encrypt / decrypt
# ------------------------------------------------------------------


def test_encrypt_decrypt_string_roundtrip() -> None:
    """字符串应能完整往返."""
    plain = "Hello, World! 你好世界"
    cipher = FieldEncryption.encrypt(plain)
    assert cipher.startswith("v")
    assert FieldEncryption.decrypt(cipher) == plain


def test_encrypt_decrypt_object_roundtrip() -> None:
    """对象应能完整往返."""
    obj = {"amount": 12345.6, "tags": ["Q1", "Q2"], "meta": {"k": "v"}}
    cipher = FieldEncryption.encrypt(obj)
    assert FieldEncryption.decrypt(cipher) == obj


def test_encrypt_rejects_none() -> None:
    """encrypt(None) 应抛 EncryptionError."""
    with pytest.raises(EncryptionError):
        FieldEncryption.encrypt(None)


def test_decrypt_rejects_non_string() -> None:
    """decrypt 非字符串应抛 EncryptionError."""
    with pytest.raises(EncryptionError):
        FieldEncryption.decrypt(123)  # type: ignore[arg-type]


def test_decrypt_handles_invalid_ciphertext() -> None:
    """密文无效应抛 EncryptionError."""
    with pytest.raises(EncryptionError):
        FieldEncryption.decrypt("vdeadbeef:notbase64:notbase64")


def test_decrypt_legacy_format() -> None:
    """旧格式（无版本前缀）应仍能解密."""
    fernet = Fernet(Fernet.generate_key())
    salt_b = b"\x00" * 16
    plain = "legacy data"
    cipher_b = fernet.encrypt(plain.encode())
    encoded = f"{base64.urlsafe_b64encode(salt_b).decode()}:{base64.urlsafe_b64encode(cipher_b).decode()}"

    # 用 fernet 的 secret 派生 key 来解密
    with patch("app.core.encryption.get_settings") as mock_settings:
        # 写一个能生成相同 fernet 的 secret
        import hashlib
        secret = "test-legacy-secret"
        mock_settings.return_value.secret_key = secret
        legacy_key = base64.urlsafe_b64encode(
            hashlib.pbkdf2_hmac(
                "sha256", secret.encode(), salt_b, iterations=100_000, dklen=32
            )
        )
        legacy_fernet = Fernet(legacy_key)

        # 用 legacy fernet 重新生成密文
        cipher_b2 = legacy_fernet.encrypt(plain.encode())
        encoded2 = f"{base64.urlsafe_b64encode(salt_b).decode()}:{base64.urlsafe_b64encode(cipher_b2).decode()}"
        assert FieldEncryption.decrypt(encoded2) == plain


def test_decrypt_wrong_key_fails() -> None:
    """用错误的 SECRET_KEY 派生时无法解密密文（防篡改）."""
    plain = "secret data"
    cipher = FieldEncryption.encrypt(plain)
    # 模拟密钥变更
    with patch("app.core.encryption.get_settings") as mock_settings:
        mock_settings.return_value.secret_key = "different-secret"
        with pytest.raises(EncryptionError):
            FieldEncryption.decrypt(cipher)


# ------------------------------------------------------------------
# re_encrypt 密钥轮换
# ------------------------------------------------------------------


def test_re_encrypt_rotates_to_current_key() -> None:
    """re_encrypt 应使用旧 key 解密，再用新 key 重新加密."""
    # 用一个固定的旧 key 加密
    old_secret = "old-secret-key-32-char-long-xxx"
    with patch("app.core.encryption.get_settings") as mock_settings:
        mock_settings.return_value.secret_key = old_secret
        plain = "sensitive data"
        old_cipher = FieldEncryption.encrypt(plain)
        old_version = get_key_version()

    # 切换到新 key
    new_secret = "new-secret-key-32-char-long-yyy"
    with patch("app.core.encryption.get_settings") as mock_settings:
        mock_settings.return_value.secret_key = new_secret
        new_cipher = re_encrypt(old_cipher, old_key=old_secret)
        new_version = get_key_version()

    assert old_version != new_version
    # 新密文应能用新 key 解密
    with patch("app.core.encryption.get_settings") as mock_settings:
        mock_settings.return_value.secret_key = new_secret
        assert FieldEncryption.decrypt(new_cipher) == plain


def test_re_encrypt_with_wrong_old_key_fails() -> None:
    """错误的 old_key 无法解密应抛 EncryptionError."""
    plain = "sensitive data"
    with patch("app.core.encryption.get_settings") as mock_settings:
        mock_settings.return_value.secret_key = "new-key"
        cipher = FieldEncryption.encrypt(plain)
        with pytest.raises(EncryptionError):
            re_encrypt(cipher, old_key="wrong-old-key")


# ------------------------------------------------------------------
# SQLAlchemy TypeDecorator
# ------------------------------------------------------------------


def test_encrypted_json_process_bind_and_result() -> None:
    """EncryptedJSON 写入应加密、读取应解密."""
    decorator = EncryptedJSON()
    obj = {"amount": 100, "currency": "CNY"}
    bound = decorator.process_bind_param(obj, None)
    assert isinstance(bound, str)
    assert bound.startswith("v")
    assert decorator.process_result_value(bound, None) == obj


def test_encrypted_json_none_passthrough() -> None:
    """EncryptedJSON 对 None 应直通."""
    decorator = EncryptedJSON()
    assert decorator.process_bind_param(None, None) is None
    assert decorator.process_result_value(None, None) is None


def test_encrypted_string_process_bind_and_result() -> None:
    """EncryptedString 写入应加密、读取应解密."""
    decorator = EncryptedString()
    plain = "sensitive"
    bound = decorator.process_bind_param(plain, None)
    assert isinstance(bound, str)
    assert bound.startswith("v")
    assert decorator.process_result_value(bound, None) == plain


def test_encrypted_string_rejects_non_string() -> None:
    """EncryptedString 写入非字符串应抛 EncryptionError."""
    decorator = EncryptedString()
    with pytest.raises(EncryptionError):
        decorator.process_bind_param(123, None)


def test_encrypted_string_none_passthrough() -> None:
    """EncryptedString 对 None 应直通."""
    decorator = EncryptedString()
    assert decorator.process_bind_param(None, None) is None
    assert decorator.process_result_value(None, None) is None


def test_encrypted_string_result_not_string_raises() -> None:
    """EncryptedString 读取到非字符串（JSON 解析）应抛 EncryptionError.

    构造：写入一段明文，但解密路径上把字符串改成非字符串（dict）。
    """
    decorator = EncryptedString()
    # 直接用 FieldEncryption 把 dict 加密成密文，然后让 EncryptedString 试图解密
    obj = {"k": "v"}
    cipher_with_obj = FieldEncryption.encrypt(obj)
    with pytest.raises(EncryptionError):
        decorator.process_result_value(cipher_with_obj, None)
