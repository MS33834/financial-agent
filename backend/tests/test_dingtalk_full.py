"""钉钉机器人（app.im.dingtalk）测试.

覆盖：签名校验（时间戳新鲜度 / HMAC-SHA256）、parse_message、build_response (markdown / text)、
send_message 主动推送。
"""

import base64
import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from app.im.dingtalk import DingTalkBot


SECRET = "dingtalk-secret-abc"


def _bot() -> DingTalkBot:
    return DingTalkBot(app_secret=SECRET)


def _valid_timestamp() -> str:
    return str(int(time.time() * 1000))


def _valid_sign(timestamp: str) -> str:
    string_to_sign = f"{timestamp}\n{SECRET}"
    mac = hmac.new(
        SECRET.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(mac).decode("utf-8")


def test_verify_signature_success() -> None:
    """正确签名应通过."""
    ts = _valid_timestamp()
    sign = _valid_sign(ts)
    bot = _bot()
    assert bot.verify_signature({}, {"timestamp": ts, "sign": sign}) is True


def test_verify_signature_no_secret_returns_false() -> None:
    """未配置 app_secret 应直接返回 False."""
    bot = DingTalkBot(app_secret="")
    assert bot.verify_signature({}, {"timestamp": _valid_timestamp(), "sign": "x"}) is False


def test_verify_signature_missing_timestamp() -> None:
    """缺 timestamp 应返回 False."""
    bot = _bot()
    assert bot.verify_signature({}, {"sign": "x"}) is False


def test_verify_signature_missing_sign() -> None:
    """缺 sign 应返回 False."""
    bot = _bot()
    assert bot.verify_signature({}, {"timestamp": _valid_timestamp()}) is False


def test_verify_signature_non_numeric_timestamp() -> None:
    """timestamp 非数字应返回 False."""
    bot = _bot()
    assert bot.verify_signature({}, {"timestamp": "abc", "sign": "x"}) is False


def test_verify_signature_stale_timestamp() -> None:
    """时间戳超过 5 分钟应被拒绝."""
    bot = _bot()
    stale_ts = str(int(time.time() * 1000) - 600_000)
    sign = _valid_sign(stale_ts)
    assert bot.verify_signature({}, {"timestamp": stale_ts, "sign": sign}) is False


def test_verify_signature_wrong_sign() -> None:
    """错误签名应返回 False."""
    bot = _bot()
    ts = _valid_timestamp()
    assert bot.verify_signature({}, {"timestamp": ts, "sign": "wrong-sign"}) is False


def test_verify_signature_uses_payload_fallback() -> None:
    """header 缺字段时应回退到 payload."""
    bot = _bot()
    ts = _valid_timestamp()
    sign = _valid_sign(ts)
    # 改用 payload 形式
    assert bot.verify_signature({"timestamp": ts, "sign": sign}, {}) is True


def test_compute_sign_no_secret() -> None:
    """无 app_secret 时应返回空字符串."""
    bot = DingTalkBot(app_secret="")
    assert bot._compute_sign("12345") == ""


def test_compute_sign_format() -> None:
    """_compute_sign 应返回 base64 编码的 HMAC-SHA256."""
    bot = _bot()
    ts = "1700000000000"
    expected = _valid_sign(ts)
    assert bot._compute_sign(ts) == expected


def test_parse_message_text() -> None:
    """parse_message 应提取 text/senderStaffId/senderNick."""
    bot = _bot()
    payload = {
        "text": {"content": "  /query 本月营收  "},
        "senderStaffId": "staff-001",
        "senderNick": "alice",
    }
    msg = bot.parse_message(payload)
    assert msg.user_id == "staff-001"
    assert msg.username == "alice"
    assert msg.text == "/query 本月营收"
    assert msg.raw_payload == payload


def test_parse_message_empty() -> None:
    """payload 缺字段时不应抛异常."""
    bot = _bot()
    msg = bot.parse_message({})
    assert msg.user_id == ""
    assert msg.text == ""


def test_build_response_text() -> None:
    """text 类型响应."""
    bot = _bot()
    resp = bot.build_response("hello")
    assert resp == {"msgtype": "text", "text": {"content": "hello"}}


def test_build_response_markdown() -> None:
    """markdown 类型响应."""
    bot = _bot()
    resp = bot.build_response("**hi**", msg_type="markdown")
    assert resp["msgtype"] == "markdown"
    assert "**hi**" in resp["markdown"]["text"]


def test_send_message_no_webhook_returns_false() -> None:
    """未配置 webhook 应返回 False."""
    bot = _bot()
    with patch("app.im.dingtalk.get_settings") as mock_settings:
        mock_settings.return_value.dingtalk_webhook = ""
        assert bot.send_message("hi") is False


def test_send_message_success() -> None:
    """配置 webhook 时应调用 send_webhook_with_retry."""
    bot = _bot()
    with patch("app.im.dingtalk.get_settings") as mock_settings, \
         patch("app.im.dingtalk.send_webhook_with_retry", return_value=True) as mock_send:
        mock_settings.return_value.dingtalk_webhook = "https://oapi.dingtalk.com/robot/send?access_token=t"
        result = bot.send_message("hello", msg_type="markdown")
    assert result is True
    mock_send.assert_called_once()
    url_arg = mock_send.call_args.args[0]
    assert "timestamp=" in url_arg
    assert "sign=" in url_arg
