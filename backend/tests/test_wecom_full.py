"""企业微信机器人（app.im.wecom）测试.

覆盖：签名校验（含 5 分钟时间窗）、extract_encrypt、AES-CBC 解密、parse_message、
build_response (markdown / text)、send_message 主动推送。
"""

import base64
import struct
import time
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.im.wecom import WeComBot, WeComDecryptError


TOKEN = "test-wecom-token-xyz"
ENCODING_AES_KEY = "GrmBxZ5RRwnsMVH3deD/+WL+VaSHWmDTVJLMuYid18M"


def _bot(token: str = TOKEN, aes: str = ENCODING_AES_KEY) -> WeComBot:
    return WeComBot(token=token, encoding_aes_key=aes)


def _aes_key_bytes() -> bytes:
    return base64.b64decode(ENCODING_AES_KEY + "=")


def _build_encrypt(plaintext: bytes, receiveid: bytes = b"corpid") -> str:
    """构造符合企业微信格式的加密 payload.

    格式: random(16) + msg_len(4 BE) + msg + receiveid + PKCS7 pad
    返回的 base64 解码后是: iv(16) + AES-CBC(body)
    """
    key = _aes_key_bytes()
    iv = b"\x00" * 16
    msg_len = struct.pack(">I", len(plaintext))
    body = b"\x00" * 16 + msg_len + plaintext + receiveid
    # PKCS7
    pad_len = 32 - (len(body) % 32)
    body += bytes([pad_len] * pad_len)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    enc = cipher.encryptor()
    # 密文 = iv + AES(body)
    return base64.b64encode(iv + enc.update(body) + enc.finalize()).decode("ascii")


def _make_xml_with_encrypt(encrypt: str) -> bytes:
    return (
        f"<xml><ToUserName><![CDATA[corpid]]></ToUserName>"
        f"<Encrypt><![CDATA[{encrypt}]]></Encrypt></xml>"
    ).encode("utf-8")


def _valid_headers(encrypt: str, raw_body: bytes) -> dict[str, str]:
    """构造带有效签名的 headers."""
    timestamp = str(int(time.time()))
    nonce = "nonce-abc"
    signature = _compute_signature(timestamp, nonce, encrypt)
    return {
        "timestamp": timestamp,
        "nonce": nonce,
        "msg_signature": signature,
    }


def _compute_signature(timestamp: str, nonce: str, encrypt: str) -> str:
    import hashlib

    parts = sorted([TOKEN, timestamp, nonce, encrypt])
    return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------
# verify_signature
# ------------------------------------------------------------------


def test_verify_signature_success() -> None:
    """正确签名应通过."""
    plain = "<xml>hello</xml>".encode("utf-8")
    encrypt = _build_encrypt(plain)
    raw_body = _make_xml_with_encrypt(encrypt)
    headers = _valid_headers(encrypt, raw_body)
    bot = _bot()
    assert bot.verify_signature({}, headers, raw_body) is True


def test_verify_signature_no_token_returns_false() -> None:
    """未配置 token 应返回 False."""
    bot = _bot(token="")
    assert bot.verify_signature({}, {}, b"<xml></xml>") is False


def test_verify_signature_missing_headers() -> None:
    """headers 缺 timestamp/nonce/signature 应返回 False."""
    bot = _bot()
    assert bot.verify_signature({}, {"timestamp": "1"}, b"<xml></xml>") is False
    assert bot.verify_signature({}, {"timestamp": "1", "nonce": "x"}, b"<xml></xml>") is False
    assert bot.verify_signature({}, {"timestamp": "1", "nonce": "x", "msg_signature": "y"}, None) is False


def test_verify_signature_non_numeric_timestamp() -> None:
    """timestamp 非数字应返回 False."""
    bot = _bot()
    headers = {"timestamp": "abc", "nonce": "x", "msg_signature": "y"}
    assert bot.verify_signature({}, headers, b"<xml></xml>") is False


def test_verify_signature_stale_timestamp() -> None:
    """时间戳超出 5 分钟应被拒绝."""
    plain = b"<xml>x</xml>"
    encrypt = _build_encrypt(plain)
    raw_body = _make_xml_with_encrypt(encrypt)
    timestamp = str(int(time.time()) - 600)
    nonce = "n"
    signature = _compute_signature(timestamp, nonce, encrypt)
    headers = {"timestamp": timestamp, "nonce": nonce, "msg_signature": signature}
    bot = _bot()
    assert bot.verify_signature({}, headers, raw_body) is False


def test_verify_signature_wrong_signature() -> None:
    """错误签名应返回 False."""
    plain = b"<xml>x</xml>"
    encrypt = _build_encrypt(plain)
    raw_body = _make_xml_with_encrypt(encrypt)
    headers = {
        "timestamp": str(int(time.time())),
        "nonce": "x",
        "msg_signature": "0" * 40,
    }
    bot = _bot()
    assert bot.verify_signature({}, headers, raw_body) is False


# ------------------------------------------------------------------
# extract_encrypt
# ------------------------------------------------------------------


def test_extract_encrypt_returns_value() -> None:
    """extract_encrypt 应正确解析 XML 中的 Encrypt 字段."""
    bot = _bot()
    raw = b'<xml><Encrypt><![CDATA[abc-def]]></Encrypt></xml>'
    assert bot.extract_encrypt(raw) == "abc-def"


def test_extract_encrypt_missing_returns_empty() -> None:
    """无 Encrypt 节点应返回空字符串."""
    bot = _bot()
    raw = b"<xml><Other>x</Other></xml>"
    assert bot.extract_encrypt(raw) == ""


def test_extract_encrypt_invalid_xml_returns_empty() -> None:
    """非法 XML 应返回空字符串而非异常."""
    bot = _bot()
    assert bot.extract_encrypt(b"not-xml") == ""


# ------------------------------------------------------------------
# decrypt
# ------------------------------------------------------------------


def test_decrypt_success() -> None:
    """正确构造的密文应能解密为 xml 字符串."""
    plain = "<xml>Hello</xml>".encode("utf-8")
    encrypt = _build_encrypt(plain)
    bot = _bot()
    result = bot.decrypt(encrypt)
    assert result == {"xml": "<xml>Hello</xml>"}


def test_decrypt_no_aes_key_raises() -> None:
    """未配置 EncodingAESKey 应抛 WeComDecryptError."""
    with patch("app.im.wecom.get_settings") as mock_settings:
        mock_settings.return_value.wecom_token = TOKEN
        mock_settings.return_value.wecom_encoding_aes_key = ""
        bot = WeComBot()
    # 构造一个长度 > 16 字节的密文，避免提前被 "密文过短" 拦截
    fake_cipher = base64.b64encode(b"\x00" * 64).decode()
    with pytest.raises(WeComDecryptError) as exc_info:
        bot.decrypt(fake_cipher)
    assert "EncodingAESKey" in str(exc_info.value)


def test_decrypt_invalid_aes_key_length_raises() -> None:
    """EncodingAESKey 长度非法应抛 WeComDecryptError."""
    bot = _bot(aes="short-key")
    with pytest.raises(WeComDecryptError):
        bot.decrypt(base64.b64encode(b"\x00" * 48).decode())


def test_decrypt_short_ciphertext_raises() -> None:
    """密文过短应抛 WeComDecryptError."""
    bot = _bot()
    with pytest.raises(WeComDecryptError) as exc_info:
        bot.decrypt(base64.b64encode(b"x").decode())
    assert "过短" in str(exc_info.value)


def test_decrypt_invalid_padding_raises() -> None:
    """填充长度非法应抛 WeComDecryptError."""
    # 构造一个 32 字节密文但 PKCS7 填充错误
    import secrets
    iv = secrets.token_bytes(16)
    body = b"\xff" * 16  # pad_len = 255 > 32
    cipher = Cipher(algorithms.AES(_aes_key_bytes()), modes.CBC(iv))
    enc = cipher.encryptor()
    payload = base64.b64encode(iv + enc.update(body) + enc.finalize()).decode()
    bot = _bot()
    with pytest.raises(WeComDecryptError) as exc_info:
        bot.decrypt(payload)
    assert "填充" in str(exc_info.value)


# ------------------------------------------------------------------
# parse_message
# ------------------------------------------------------------------


def test_parse_message_text() -> None:
    """parse_message 应从 xml 中提取 FromUserName/Content."""
    bot = _bot()
    payload = {
        "xml": (
            "<xml>"
            "<FromUserName><![CDATA[user-1]]></FromUserName>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[  /approve 1  ]]></Content>"
            "</xml>"
        )
    }
    msg = bot.parse_message(payload)
    assert msg.user_id == "user-1"
    assert msg.username == "user-1"
    assert msg.text == "/approve 1"


def test_parse_message_non_text_returns_empty_content() -> None:
    """非 text 消息类型的 Content 应为空."""
    bot = _bot()
    payload = {
        "xml": (
            "<xml>"
            "<FromUserName><![CDATA[u]]></FromUserName>"
            "<MsgType><![CDATA[image]]></MsgType>"
            "</xml>"
        )
    }
    msg = bot.parse_message(payload)
    assert msg.text == ""


def test_parse_message_invalid_xml() -> None:
    """无法解析的 xml 应返回 raw_payload 而不抛异常."""
    bot = _bot()
    msg = bot.parse_message({"xml": "not-xml"})
    assert msg.raw_payload == {"xml": "not-xml"}


# ------------------------------------------------------------------
# build_response
# ------------------------------------------------------------------


def test_build_response_text() -> None:
    bot = _bot()
    resp = bot.build_response("hello")
    assert resp == {"msg_type": "text", "content": {"content": "hello"}}


def test_build_response_markdown() -> None:
    bot = _bot()
    resp = bot.build_response("# title", msg_type="markdown")
    assert resp == {"msg_type": "markdown", "content": "# title"}


# ------------------------------------------------------------------
# send_message
# ------------------------------------------------------------------


def test_send_message_no_webhook_returns_false() -> None:
    bot = _bot()
    with patch("app.im.wecom.get_settings") as mock_settings:
        mock_settings.return_value.wecom_webhook = ""
        assert bot.send_message("hi") is False


def test_send_message_success() -> None:
    bot = _bot()
    with patch("app.im.wecom.get_settings") as mock_settings, \
         patch("app.im.wecom.send_webhook_with_retry", return_value=True) as mock_send:
        mock_settings.return_value.wecom_webhook = "https://qyapi.weixin.qq.com/hook"
        result = bot.send_message("hello", msg_type="markdown")
    assert result is True
    mock_send.assert_called_once()
    url_arg, body_arg = mock_send.call_args.args
    # body 是字节流，解析后为 {"msg_type": ..., "content": ...}
    import json as _json

    decoded = _json.loads(body_arg)
    assert decoded["msg_type"] == "markdown"
