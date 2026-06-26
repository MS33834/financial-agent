"""Dify Tools 路由补充测试.

覆盖 nl2sql / create_report / approve_report / parse_document 四个 Tool
的认证、鉴权与调用链路，使用 Mock 隔离服务层与 Celery 任务。
"""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.user import User
from app.security import get_password_hash

DIFY_API_KEY = "tool-secret"


@pytest.fixture(autouse=True)
def _restore_settings() -> Generator[None, None, None]:
    """每个测试后清除配置缓存，避免环境变量交叉污染."""
    yield
    get_settings.cache_clear()


@pytest.fixture
def dify_api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """配置 Dify Tool API Key 并刷新配置缓存."""
    monkeypatch.setenv("DIFY_TOOL_API_KEY", DIFY_API_KEY)
    get_settings.cache_clear()
    return DIFY_API_KEY


@pytest.fixture
def dify_user(db_session: Session) -> User:
    """创建供 Dify Tools 测试使用的用户与租户."""
    tenant = Tenant(name="Dify Tools Tenant", code="dify-tools")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        username="dify-tools-user",
        email="dify-tools@example.com",
        hashed_password=get_password_hash("testpass"),
        role="admin",
        is_active="Y",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _payload(user: User, **extra: Any) -> dict[str, Any]:
    """构造 Dify Tool 请求体（含 tenant_id / user_id）."""
    data: dict[str, Any] = {
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.id),
    }
    data.update(extra)
    return data


def test_dify_tools_not_configured_returns_501(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未配置 DIFY_TOOL_API_KEY 时应返回 501."""
    monkeypatch.delenv("DIFY_TOOL_API_KEY", raising=False)
    get_settings.cache_clear()

    resp = client.post("/api/v1/dify/tools/nl2sql", json={"question": "x"})
    assert resp.status_code == 501


def test_dify_tools_missing_api_key_returns_401(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    dify_user: User,
) -> None:
    """配置了 API Key 但请求未携带 X-API-Key 时应返回 401."""
    monkeypatch.setenv("DIFY_TOOL_API_KEY", DIFY_API_KEY)
    get_settings.cache_clear()

    resp = client.post(
        "/api/v1/dify/tools/nl2sql",
        json=_payload(dify_user, question="营收"),
    )
    assert resp.status_code == 401


def test_dify_tools_invalid_api_key_returns_401(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    dify_user: User,
) -> None:
    """错误的 X-API-Key 应返回 401."""
    monkeypatch.setenv("DIFY_TOOL_API_KEY", DIFY_API_KEY)
    get_settings.cache_clear()

    resp = client.post(
        "/api/v1/dify/tools/nl2sql",
        json=_payload(dify_user, question="营收"),
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 401


def test_dify_tools_nl2sql_success(
    client: TestClient,
    dify_api_key: str,
    dify_user: User,
) -> None:
    """携带正确 API Key 时 nl2sql 应返回成功结果."""
    with patch("app.routers.dify_tools.QueryService") as mock_cls:
        mock_service = MagicMock()
        mock_service.nl2sql.return_value = {
            "question": "营收",
            "sql": "SELECT revenue FROM financial_reports",
            "data": [{"revenue": 1_000_000}],
        }
        mock_cls.return_value = mock_service

        resp = client.post(
            "/api/v1/dify/tools/nl2sql",
            json=_payload(dify_user, question="营收"),
            headers={"X-API-Key": dify_api_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["data"]["sql"].startswith("SELECT")
    assert body["data"]["data"][0]["revenue"] == 1_000_000


def test_dify_tools_nl2sql_user_not_found(
    client: TestClient,
    dify_api_key: str,
    dify_user: User,
) -> None:
    """user_id 不存在时应返回 404."""
    payload = _payload(dify_user, question="营收")
    payload["user_id"] = "nonexistent-user"
    resp = client.post(
        "/api/v1/dify/tools/nl2sql",
        json=payload,
        headers={"X-API-Key": dify_api_key},
    )
    assert resp.status_code == 404


def test_dify_tools_create_report_success(
    client: TestClient,
    dify_api_key: str,
    dify_user: User,
) -> None:
    """create_report 应委托 report_service 并返回报告摘要."""
    fake_report = MagicMock()
    fake_report.id = "rep-1"
    fake_report.status = "pending"
    fake_report.title = "2025 Q2 利润表"

    with patch("app.routers.dify_tools.create_report_task", return_value=fake_report) as mock:
        resp = client.post(
            "/api/v1/dify/tools/create_report",
            json=_payload(
                dify_user,
                title="2025 Q2 利润表",
                report_type="profit",
                parameters={"year": 2025, "period": "Q2"},
            ),
            headers={"X-API-Key": dify_api_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["report_id"] == "rep-1"
    assert body["data"]["status"] == "pending"
    # 验证服务层以传入用户调用
    assert mock.call_args.kwargs["user"].id == dify_user.id


def test_dify_tools_approve_report_success(
    client: TestClient,
    dify_api_key: str,
    dify_user: User,
) -> None:
    """approve_report 应记录审批并返回审批动作."""
    fake_report = MagicMock()
    fake_report.id = "rep-2"
    fake_report.status = "approved"
    fake_approval = MagicMock()
    fake_approval.id = "appr-1"
    fake_approval.action = "approve"

    with (
        patch("app.routers.dify_tools.get_report", return_value=fake_report),
        patch("app.routers.dify_tools.record_approval", return_value=fake_approval) as mock_rec,
    ):
        resp = client.post(
            "/api/v1/dify/tools/approve_report",
            json=_payload(
                dify_user,
                report_id="rep-2",
                action="approve",
                comments="同意",
            ),
            headers={"X-API-Key": dify_api_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["approval_id"] == "appr-1"
    assert body["data"]["action"] == "approve"
    assert mock_rec.call_args.kwargs["action"] == "approve"


def test_dify_tools_approve_report_not_found(
    client: TestClient,
    dify_api_key: str,
    dify_user: User,
) -> None:
    """审批不存在的报告应返回 404."""
    with patch("app.routers.dify_tools.get_report", return_value=None):
        resp = client.post(
            "/api/v1/dify/tools/approve_report",
            json=_payload(dify_user, report_id="missing", action="approve"),
            headers={"X-API-Key": dify_api_key},
        )
    assert resp.status_code == 404


def test_dify_tools_approve_report_approval_error(
    client: TestClient,
    dify_api_key: str,
    dify_user: User,
) -> None:
    """record_approval 抛出 ApprovalError 时应返回失败结构而非 500."""
    from app.services.approval_service import ApprovalError

    fake_report = MagicMock()
    fake_report.id = "rep-3"
    fake_report.status = "approved"

    with (
        patch("app.routers.dify_tools.get_report", return_value=fake_report),
        patch(
            "app.routers.dify_tools.record_approval",
            side_effect=ApprovalError("当前报告状态不允许审核"),
        ),
    ):
        resp = client.post(
            "/api/v1/dify/tools/approve_report",
            json=_payload(dify_user, report_id="rep-3", action="approve"),
            headers={"X-API-Key": dify_api_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "不允许审核" in body["error"]


def test_dify_tools_parse_document_success(
    client: TestClient,
    dify_api_key: str,
    dify_user: User,
    db_session: Session,
) -> None:
    """parse_document 应校验归属后触发解析任务并返回 task_id."""
    doc = Document(
        tenant_id=dify_user.tenant_id,
        filename="report.xlsx",
        storage_key="documents/key",
        status="pending",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    fake_task = MagicMock()
    fake_task.id = "celery-task-1"

    with patch("app.routers.dify_tools.parse_document_task") as mock_task:
        mock_task.delay.return_value = fake_task
        resp = client.post(
            "/api/v1/dify/tools/parse_document",
            json=_payload(dify_user, document_id=doc.id),
            headers={"X-API-Key": dify_api_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["document_id"] == doc.id
    assert body["data"]["task_id"] == "celery-task-1"
    mock_task.delay.assert_called_once_with(doc.id)


def test_dify_tools_parse_document_not_found(
    client: TestClient,
    dify_api_key: str,
    dify_user: User,
) -> None:
    """解析不存在的文档应返回 404."""
    resp = client.post(
        "/api/v1/dify/tools/parse_document",
        json=_payload(dify_user, document_id="missing-doc"),
        headers={"X-API-Key": dify_api_key},
    )
    assert resp.status_code == 404


def test_dify_tools_parse_document_forbidden(
    client: TestClient,
    dify_api_key: str,
    dify_user: User,
    db_session: Session,
) -> None:
    """解析其他租户的文档应返回 403."""
    other_tenant = Tenant(name="Other Tenant", code="other")
    db_session.add(other_tenant)
    db_session.commit()
    db_session.refresh(other_tenant)

    doc = Document(
        tenant_id=other_tenant.id,
        filename="other.xlsx",
        storage_key="documents/other",
        status="pending",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    resp = client.post(
        "/api/v1/dify/tools/parse_document",
        json=_payload(dify_user, document_id=doc.id),
        headers={"X-API-Key": dify_api_key},
    )
    assert resp.status_code == 403
