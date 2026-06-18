"""IM 机器人测试."""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.im.commands import format_approval_result, parse_command
from app.im.dingtalk import DingTalkBot
from app.models.tenant import Tenant
from app.models.user import User
from app.routers.im import _get_user_by_im_id
from app.security import get_password_hash


@pytest.fixture
def dingtalk_secret() -> str:
    return "test-secret"


def _compute_dingtalk_sign(secret: str, timestamp: str) -> str:
    """计算钉钉签名."""
    import base64
    import hashlib
    import hmac

    string_to_sign = f"{timestamp}\n{secret}"
    mac = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(mac).decode("utf-8")


def test_parse_command() -> None:
    """命令解析正确."""
    cmd = parse_command("/report profit year=2025 period=Q2")
    assert cmd.name == "report"
    assert cmd.args == ["profit"]
    assert cmd.kwargs == {"year": "2025", "period": "Q2"}


def test_parse_command_invalid() -> None:
    """非命令文本抛出异常."""
    with pytest.raises(ValueError):
        parse_command("hello")


def test_dingtalk_verify_signature(dingtalk_secret: str) -> None:
    """钉钉签名验证通过."""
    bot = DingTalkBot(app_secret=dingtalk_secret)
    timestamp = "1234567890"
    sign = _compute_dingtalk_sign(dingtalk_secret, timestamp)
    assert bot.verify_signature({}, {"timestamp": timestamp, "sign": sign}) is True


def test_dingtalk_verify_signature_invalid(dingtalk_secret: str) -> None:
    """错误签名验证失败."""
    bot = DingTalkBot(app_secret=dingtalk_secret)
    assert bot.verify_signature({}, {"timestamp": "123", "sign": "bad"}) is False


def test_dingtalk_build_response_text() -> None:
    """钉钉文本响应格式正确."""
    bot = DingTalkBot(app_secret="test")
    resp = bot.build_response("hello")
    assert resp["msgtype"] == "text"
    assert resp["text"]["content"] == "hello"


def test_dingtalk_build_response_markdown() -> None:
    """钉钉 markdown 响应格式正确."""
    bot = DingTalkBot(app_secret="test")
    resp = bot.build_response("**bold**", msg_type="markdown")
    assert resp["msgtype"] == "markdown"
    assert resp["markdown"]["text"] == "**bold**"


def test_dingtalk_webhook_missing_signature(client: TestClient) -> None:
    """缺少签名返回 401."""
    resp = client.post("/api/v1/im/dingtalk", json={"text": {"content": "/help"}})
    assert resp.status_code == 401


@contextmanager
def _mock_bot() -> Iterator[None]:
    """统一 Mock 钉钉签名验证."""
    with patch.multiple(
        DingTalkBot,
        __init__=lambda _self, _app_secret=None: None,
        verify_signature=lambda _self, _payload, _headers: True,
    ):
        yield


def test_dingtalk_webhook_help(client: TestClient) -> None:
    """/help 命令返回帮助文本."""
    with _mock_bot(), patch.object(DingTalkBot, "build_response") as mock_build:
        mock_build.return_value = {"msgtype": "text", "text": {"content": "help"}}
        client.post(
            "/api/v1/im/dingtalk",
            json={"text": {"content": "/help"}, "senderStaffId": "user1"},
        )
        assert mock_build.called
        call_args = mock_build.call_args[0]
        assert "/query" in call_args[0]


def test_dingtalk_webhook_empty_message(client: TestClient) -> None:
    """空消息返回友好提示."""
    with _mock_bot():
        resp = client.post(
            "/api/v1/im/dingtalk",
            json={"text": {"content": "   "}, "senderStaffId": "user1"},
        )
        assert resp.status_code == 200
        assert "收到空消息" in resp.json()["text"]["content"]


def test_dingtalk_webhook_user_not_found(client: TestClient) -> None:
    """未绑定用户返回提示."""
    with _mock_bot():
        resp = client.post(
            "/api/v1/im/dingtalk",
            json={"text": {"content": "/query 营收"}, "senderStaffId": "unknown_user"},
        )
        assert resp.status_code == 200
        assert "未找到对应的系统用户" in resp.json()["text"]["content"]


def test_dingtalk_webhook_user_found_by_attributes(
    db_session: Session, client: TestClient
) -> None:
    """通过 attributes 中的 dingtalk_user_id 匹配用户."""
    tenant = Tenant(name="IM Test", code="im-test")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        username="dinguser",
        hashed_password=get_password_hash("pass"),
        role="admin",
        is_active="Y",
        attributes={"dingtalk_user_id": "ding123"},
    )
    db_session.add(user)
    db_session.commit()

    assert _get_user_by_im_id(db_session, "ding123") is not None

    with _mock_bot(), patch("app.routers.im.handle_command", return_value="查询结果"):
        resp = client.post(
            "/api/v1/im/dingtalk",
            json={"text": {"content": "/query 营收"}, "senderStaffId": "ding123"},
        )
        assert resp.status_code == 200
        assert resp.json()["text"]["content"] == "查询结果"


def test_dingtalk_parse_message() -> None:
    """钉钉消息解析正确."""
    bot = DingTalkBot(app_secret="test")
    payload = {
        "senderStaffId": "user001",
        "senderNick": "张三",
        "text": {"content": " /query 营收 "},
    }
    msg = bot.parse_message(payload)
    assert msg.user_id == "user001"
    assert msg.username == "张三"
    assert msg.text == "/query 营收"


def test_format_approval_result() -> None:
    """审批结果格式化正确."""
    result = {
        "success": True,
        "data": {"report_id": "r-1", "action": "approved"},
    }
    text = format_approval_result(result)
    assert "r-1" in text
    assert "approved" in text
