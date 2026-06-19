"""IM 机器人测试."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.im.commands import format_approval_result, parse_command
from app.im.dingtalk import DingTalkBot
from app.im.feishu import FeishuBot
from app.models.report import Report
from app.models.tenant import Tenant
from app.models.user import User
from app.routers.im import _get_user_by_im_id
from app.security import get_password_hash
from app.tasks.report_tasks import generate_report_task


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


@pytest.fixture
def feishu_encrypt_key() -> str:
    return "test-encrypt-key-32-char-long-xx"


def _compute_feishu_sign(encrypt_key: str, timestamp: str, nonce: str, body: bytes) -> str:
    """计算飞书事件订阅签名."""
    import hashlib

    sign_str = f"{timestamp}{nonce}{encrypt_key}{body.decode('utf-8')}"
    return hashlib.sha256(sign_str.encode("utf-8")).hexdigest()


def test_feishu_verify_signature(feishu_encrypt_key: str) -> None:
    """飞书签名验证通过."""
    bot = FeishuBot(encrypt_key=feishu_encrypt_key)
    timestamp = "1234567890"
    nonce = "abc123"
    body = b'{"type":"url_verification","challenge":"c1"}'
    sign = _compute_feishu_sign(feishu_encrypt_key, timestamp, nonce, body)
    assert bot.verify_signature({}, {"X-Lark-Request-Timestamp": timestamp, "X-Lark-Request-Nonce": nonce, "X-Lark-Signature": sign}, raw_body=body) is True


def test_feishu_verify_signature_invalid(feishu_encrypt_key: str) -> None:
    """错误飞书签名验证失败."""
    bot = FeishuBot(encrypt_key=feishu_encrypt_key)
    assert bot.verify_signature({}, {"X-Lark-Request-Timestamp": "1", "X-Lark-Request-Nonce": "n", "X-Lark-Signature": "bad"}, raw_body=b"{}") is False


def test_feishu_parse_message() -> None:
    """飞书消息解析正确."""
    bot = FeishuBot(encrypt_key="test")
    payload = {
        "schema": "2.0",
        "header": {"tenant_key": "t1"},
        "event": {
            "message": {
                "message_type": "text",
                "content": '{"text":" /query 营收 "}',
            },
            "sender": {
                "sender_id": {"user_id": "u001"},
                "sender_type": "user",
            },
        },
    }
    msg = bot.parse_message(payload)
    assert msg.user_id == "u001"
    assert msg.tenant_id == "t1"
    assert msg.text == "/query 营收"


def test_feishu_build_response() -> None:
    """飞书响应格式正确."""
    bot = FeishuBot(encrypt_key="test")
    resp = bot.build_response("hello")
    assert resp["msg_type"] == "text"
    assert resp["content"]["text"] == "hello"


def test_feishu_webhook_challenge(client: TestClient, feishu_encrypt_key: str) -> None:
    """飞书 URL 验证返回 challenge."""
    body = b'{"type":"url_verification","challenge":"xyz","token":"t"}'
    timestamp = "1234567890"
    nonce = "n1"
    sign = _compute_feishu_sign(feishu_encrypt_key, timestamp, nonce, body)
    resp = client.post(
        "/api/v1/im/feishu",
        content=body,
        headers={
            "X-Lark-Request-Timestamp": timestamp,
            "X-Lark-Request-Nonce": nonce,
            "X-Lark-Signature": sign,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["challenge"] == "xyz"


def test_feishu_webhook_user_found_by_attributes(
    db_session: Session, client: TestClient, feishu_encrypt_key: str
) -> None:
    """通过 attributes 中的 feishu_user_id 匹配用户."""
    tenant = Tenant(name="Feishu Test", code="feishu-test")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        username="feishuuser",
        hashed_password=get_password_hash("pass"),
        role="admin",
        is_active="Y",
        attributes={"feishu_user_id": "fsu001"},
    )
    db_session.add(user)
    db_session.commit()

    assert _get_user_by_im_id(db_session, "fsu001", platform="feishu") is not None

    payload = {
        "schema": "2.0",
        "header": {"tenant_key": "t1"},
        "event": {
            "message": {
                "message_type": "text",
                "content": '{"text":"/query 营收"}',
            },
            "sender": {
                "sender_id": {"user_id": "fsu001"},
                "sender_type": "user",
            },
        },
    }
    body = json.dumps(payload).encode("utf-8")
    timestamp = "1234567890"
    nonce = "n1"
    sign = _compute_feishu_sign(feishu_encrypt_key, timestamp, nonce, body)

    with patch("app.routers.im.handle_command", return_value="查询结果"):
        resp = client.post(
            "/api/v1/im/feishu",
            content=body,
            headers={
                "X-Lark-Request-Timestamp": timestamp,
                "X-Lark-Request-Nonce": nonce,
                "X-Lark-Signature": sign,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["content"]["text"] == "查询结果"


def _create_reviewing_report(
    db_session: Session,
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    """创建报告并将其置为 reviewing 状态，返回 report_id."""
    monkeypatch.setattr(generate_report_task, "delay", lambda _report_id: None)

    resp = client.post(
        "/api/v1/reports",
        json={"title": "IM 审批测试", "report_type": "cash"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    report_id = cast(str, resp.json()["data"]["id"])

    report = db_session.query(Report).filter(Report.id == report_id).first()
    assert report is not None
    report.status = "reviewing"
    db_session.commit()
    return report_id


def test_dingtalk_webhook_approve_report(
    db_session: Session,
    client: TestClient,
    auth_headers: dict[str, str],
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """通过钉钉机器人审批报告."""
    test_user.attributes = {"dingtalk_user_id": "ding_approver"}
    db_session.commit()
    report_id = _create_reviewing_report(db_session, client, auth_headers, monkeypatch)

    with _mock_bot():
        resp = client.post(
            "/api/v1/im/dingtalk",
            json={
                "text": {"content": f"/approve report_id={report_id} comment=同意"},
                "senderStaffId": "ding_approver",
            },
        )
        assert resp.status_code == 200
        assert "approve" in resp.json()["text"]["content"]

    report_resp = client.get(f"/api/v1/reports/{report_id}", headers=auth_headers)
    assert report_resp.json()["data"]["status"] == "approved"


def test_dingtalk_webhook_reject_report(
    db_session: Session,
    client: TestClient,
    auth_headers: dict[str, str],
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """通过钉钉机器人驳回报告."""
    test_user.attributes = {"dingtalk_user_id": "ding_approver"}
    db_session.commit()
    report_id = _create_reviewing_report(db_session, client, auth_headers, monkeypatch)

    with _mock_bot():
        resp = client.post(
            "/api/v1/im/dingtalk",
            json={
                "text": {"content": f"/reject report_id={report_id} comment=数据有误"},
                "senderStaffId": "ding_approver",
            },
        )
        assert resp.status_code == 200
        assert "reject" in resp.json()["text"]["content"]

    report_resp = client.get(f"/api/v1/reports/{report_id}", headers=auth_headers)
    assert report_resp.json()["data"]["status"] == "rejected"


def test_dingtalk_webhook_pending_reports(
    db_session: Session,
    client: TestClient,
    auth_headers: dict[str, str],
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """通过钉钉机器人查看待审报告列表."""
    test_user.attributes = {"dingtalk_user_id": "ding_approver"}
    db_session.commit()
    report_id = _create_reviewing_report(db_session, client, auth_headers, monkeypatch)

    with _mock_bot():
        resp = client.post(
            "/api/v1/im/dingtalk",
            json={"text": {"content": "/pending"}, "senderStaffId": "ding_approver"},
        )
        assert resp.status_code == 200
        assert report_id in resp.json()["text"]["content"]


def test_dingtalk_webhook_approve_non_reviewing_report(
    db_session: Session,
    client: TestClient,
    auth_headers: dict[str, str],
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """对非 reviewing 状态报告审批返回友好提示."""
    monkeypatch.setattr(generate_report_task, "delay", lambda _report_id: None)
    test_user.attributes = {"dingtalk_user_id": "ding_approver"}
    db_session.commit()

    resp = client.post(
        "/api/v1/reports",
        json={"title": "未生成报告", "report_type": "cash"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    report_id = resp.json()["data"]["id"]

    with _mock_bot():
        resp = client.post(
            "/api/v1/im/dingtalk",
            json={
                "text": {"content": f"/approve report_id={report_id}"},
                "senderStaffId": "ding_approver",
            },
        )
        assert resp.status_code == 200
        assert "不处于待审核状态" in resp.json()["text"]["content"]


def test_dingtalk_webhook_approve_viewer_forbidden(
    db_session: Session,
    client: TestClient,
    viewer_auth_headers: dict[str, str],
    viewer_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """viewer 角色通过 IM 审批应提示权限不足."""
    monkeypatch.setattr(generate_report_task, "delay", lambda _report_id: None)
    viewer_user.attributes = {"dingtalk_user_id": "ding_viewer"}
    db_session.commit()

    resp = client.post(
        "/api/v1/reports",
        json={"title": "viewer 审批测试", "report_type": "cash"},
        headers=viewer_auth_headers,
    )
    assert resp.status_code == 201
    report_id = cast(str, resp.json()["data"]["id"])

    report = db_session.query(Report).filter(Report.id == report_id).first()
    assert report is not None
    report.status = "reviewing"
    db_session.commit()

    with _mock_bot():
        resp = client.post(
            "/api/v1/im/dingtalk",
            json={
                "text": {"content": f"/approve report_id={report_id}"},
                "senderStaffId": "ding_viewer",
            },
        )
        assert resp.status_code == 200
        assert "权限不足" in resp.json()["text"]["content"]
