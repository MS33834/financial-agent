"""飞书机器人（app.im.feishu）测试.

覆盖：签名校验（5 分钟时间窗 + SHA-256）、AES-CBC 解密、parse_message、
build_response (markdown / text)、send_message 主动推送。
"""

import base64
import hashlib
import json
import time
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.im.feishu import FeishuBot, FeishuDecryptError

ENCRYPT_KEY = "test-feishu-encrypt-key-32-char-long-xx"


def _bot(key: str = ENCRYPT_KEY) -> FeishuBot:
    return FeishuBot(encrypt_key=key)


def _aes_key_bytes(key: str) -> bytes:
    return hashlib.sha256(key.encode("utf-8")).digest()[:32]


def _aes_encrypt(plaintext: bytes, key_str: str) -> str:
    """构造符合飞书格式的加密 payload.

    格式: iv(16) + AES-256-CBC(plaintext + PKCS7 pad)，结果 base64 编码。
    """
    iv = b"\x00" * 16
    key = _aes_key_bytes(key_str)
    pad_len = 16 - (len(plaintext) % 16)
    body = plaintext + bytes([pad_len] * pad_len)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    enc = cipher.encryptor()
    return base64.b64encode(iv + enc.update(body) + enc.finalize()).decode("ascii")


def _sign(timestamp: str, nonce: str, body: str, key: str = ENCRYPT_KEY) -> str:
    sign_str = f"{timestamp}{nonce}{key}{body}"
    return hashlib.sha256(sign_str.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------
# verify_signature
# ------------------------------------------------------------------


def test_verify_signature_success() -> None:
    """正确签名应通过."""
    body = '{"event":"x"}'
    ts = str(int(time.time()))
    nonce = "nonce-001"
    signature = _sign(ts, nonce, body)
    headers = {
        "X-Lark-Request-Timestamp": ts,
        "X-Lark-Request-Nonce": nonce,
        "X-Lark-Signature": signature,
    }
    bot = _bot()
    assert bot.verify_signature({}, headers, body.encode("utf-8")) is True


def test_verify_signature_no_key_returns_false() -> None:
    """未配置 encrypt_key 应返回 False."""
    bot = _bot(key="")
    assert bot.verify_signature({}, {}, b"{}") is False


def test_verify_signature_no_body_returns_false() -> None:
    """raw_body 为空应返回 False."""
    bot = _bot()
    assert bot.verify_signature({}, {"X-Lark-Signature": "x"}, None) is False


def test_verify_signature_missing_headers() -> None:
    """缺任一 header 字段应返回 False."""
    bot = _bot()
    assert bot.verify_signature({}, {"X-Lark-Request-Timestamp": "1", "X-Lark-Request-Nonce": "x"}, b"{}") is False
    assert bot.verify_signature({}, {"X-Lark-Request-Timestamp": "1", "X-Lark-Signature": "y"}, b"{}") is False
    assert bot.verify_signature({}, {"X-Lark-Request-Nonce": "x", "X-Lark-Signature": "y"}, b"{}") is False


def test_verify_signature_non_numeric_timestamp() -> None:
    bot = _bot()
    headers = {
        "X-Lark-Request-Timestamp": "abc",
        "X-Lark-Request-Nonce": "x",
        "X-Lark-Signature": "y",
    }
    assert bot.verify_signature({}, headers, b"{}") is False


def test_verify_signature_stale_timestamp() -> None:
    bot = _bot()
    ts = str(int(time.time()) - 600)
    headers = {
        "X-Lark-Request-Timestamp": ts,
        "X-Lark-Request-Nonce": "x",
        "X-Lark-Signature": "y",
    }
    assert bot.verify_signature({}, headers, b"{}") is False


def test_verify_signature_wrong_signature() -> None:
    bot = _bot()
    ts = str(int(time.time()))
    headers = {
        "X-Lark-Request-Timestamp": ts,
        "X-Lark-Request-Nonce": "x",
        "X-Lark-Signature": "0" * 64,
    }
    assert bot.verify_signature({}, headers, b"{}") is False


# ------------------------------------------------------------------
# decrypt
# ------------------------------------------------------------------


def test_decrypt_success() -> None:
    """正确密文应能解密为 JSON dict."""
    payload = {"event": "x", "msg": "hello"}
    plaintext = json.dumps(payload).encode("utf-8")
    encrypt = _aes_encrypt(plaintext, ENCRYPT_KEY)
    bot = _bot()
    assert bot.decrypt(encrypt) == payload


def test_decrypt_no_key_raises() -> None:
    with patch("app.im.feishu.get_settings") as mock_settings:
        mock_settings.return_value.feishu_encrypt_key = ""
        bot = FeishuBot()
    # 构造一个长度 >= 16 字节的密文，避免提前被 "密文过短" 拦截
    fake_cipher = base64.b64encode(b"\x00" * 64).decode()
    with pytest.raises(FeishuDecryptError) as exc_info:
        bot.decrypt(fake_cipher)
    assert "encrypt_key" in str(exc_info.value)


def test_decrypt_short_ciphertext_raises() -> None:
    bot = _bot()
    with pytest.raises(FeishuDecryptError) as exc_info:
        bot.decrypt(base64.b64encode(b"x").decode())
    assert "过短" in str(exc_info.value)


def test_decrypt_invalid_padding_raises() -> None:
    """填充长度非法应抛 FeishuDecryptError."""
    iv = b"\x00" * 16
    body = b"\xff" * 16  # pad_len = 255 > 16
    cipher = Cipher(algorithms.AES(_aes_key_bytes(ENCRYPT_KEY)), modes.CBC(iv))
    enc = cipher.encryptor()
    payload = base64.b64encode(iv + enc.update(body) + enc.finalize()).decode()
    bot = _bot()
    with pytest.raises(FeishuDecryptError) as exc_info:
        bot.decrypt(payload)
    assert "填充" in str(exc_info.value)


# ------------------------------------------------------------------
# parse_message
# ------------------------------------------------------------------


def test_parse_message_v2_schema_text() -> None:
    """v2 schema 文本消息应能正确解析."""
    bot = _bot()
    payload = {
        "schema": "2.0",
        "header": {"tenant_key": "tenant-7"},
        "event": {
            "sender": {
                "sender_id": {"user_id": "u-007"},
                "sender_type": "user",
            },
            "message": {
                "content": json.dumps({"text": "  /query 本月营收  "}),
            },
        },
    }
    msg = bot.parse_message(payload)
    assert msg.user_id == "u-007"
    assert msg.username == "user"
    assert msg.tenant_id == "tenant-7"
    assert msg.text == "/query 本月营收"


def test_parse_message_invalid_content_json() -> None:
    """content 字段非 JSON 时应安全降级为空 content."""
    bot = _bot()
    payload = {
        "event": {
            "sender": {"sender_id": {"user_id": "u"}},
            "message": {"content": "not-a-json"},
        }
    }
    msg = bot.parse_message(payload)
    assert msg.user_id == "u"
    assert msg.text == ""


# ------------------------------------------------------------------
# build_response
# ------------------------------------------------------------------


def test_build_response_text() -> None:
    bot = _bot()
    resp = bot.build_response("hello")
    assert resp == {"msg_type": "text", "content": {"text": "hello"}}


def test_build_response_markdown() -> None:
    bot = _bot()
    resp = bot.build_response("# title", msg_type="markdown")
    assert resp["msg_type"] == "interactive"
    assert resp["card"]["elements"][0]["tag"] == "markdown"


# ------------------------------------------------------------------
# send_message
# ------------------------------------------------------------------


def test_send_message_no_webhook_returns_false() -> None:
    bot = _bot()
    with patch("app.im.feishu.get_settings") as mock_settings:
        mock_settings.return_value.feishu_webhook = ""
        assert bot.send_message("hi") is False


def test_send_message_success() -> None:
    bot = _bot()
    with patch("app.im.feishu.get_settings") as mock_settings, \
         patch("app.im.feishu.send_webhook_with_retry", return_value=True) as mock_send:
        mock_settings.return_value.feishu_webhook = "https://open.feishu.cn/hook"
        result = bot.send_message("hello", msg_type="markdown")
    assert result is True
    mock_send.assert_called_once()
