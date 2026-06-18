"""Dify 集成测试.

覆盖 DifyClient 调用与后端 Tools API 的认证/调用链路。
由于沙箱通常无法启动完整 Dify，本测试使用 Mock 验证接口契约。
"""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dify.client import DifyClient, DifyClientError
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User
from app.security import get_password_hash


@pytest.fixture(autouse=True)
def _restore_settings() -> Generator[None, None, None]:
    """每个测试后清除配置缓存，避免环境变量交叉污染."""
    yield
    get_settings.cache_clear()


def _mock_response(json_data: dict[str, Any], status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.text = str(json_data)
    mock.raise_for_status.return_value = None
    return mock


def test_dify_client_requires_config() -> None:
    """未配置 base_url/api_key 时应抛出异常."""
    with (
        patch.object(get_settings(), "dify_base_url", None),
        patch.object(get_settings(), "dify_api_key", None),
        pytest.raises(DifyClientError, match="DIFY_BASE_URL"),
    ):
        DifyClient()


def test_dify_client_run_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """DifyClient 应正确调用 Workflow Run API."""
    monkeypatch.setenv("DIFY_BASE_URL", "http://dify.test/v1")
    monkeypatch.setenv("DIFY_API_KEY", "test-api-key")
    get_settings.cache_clear()

    client = DifyClient()
    expected = {
        "data": {
            "outputs": {
                "answer": "2025 年 Q2 营业收入为 1,000,000 元。",
            },
        },
    }

    with patch("app.dify.client.httpx.post") as mock_post:
        mock_post.return_value = _mock_response(expected)
        result = client.run_workflow(inputs={"question": "Q2 营收"})

    assert result == expected
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["inputs"] == {"question": "Q2 营收"}
    assert call_kwargs["json"]["response_mode"] == "blocking"


def test_dify_tools_requires_api_key() -> None:
    """缺少或错误的 X-API-Key 应返回 401/501."""
    client = TestClient(app)
    resp = client.post("/api/v1/dify/tools/nl2sql", json={"question": "test"})
    assert resp.status_code == 501


@pytest.fixture
def dify_tool_user(db_session: Session) -> User:
    """创建供 Dify Tools 测试使用的用户."""
    tenant = Tenant(name="Dify Tool Tenant", code="dify-tool")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        username="dify-tool-user",
        email="dify-tool@example.com",
        hashed_password=get_password_hash("testpass"),
        role="admin",
        is_active="Y",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_dify_tools_nl2sql(
    client: TestClient,
    dify_tool_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """携带正确 X-API-Key 时，nl2sql Tool 应返回结果."""
    monkeypatch.setenv("DIFY_TOOL_API_KEY", "tool-secret")
    get_settings.cache_clear()

    payload = {
        "tenant_id": str(dify_tool_user.tenant_id),
        "user_id": str(dify_tool_user.id),
        "question": "2025年Q2营业收入是多少？",
    }

    with patch("app.routers.dify_tools.QueryService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.nl2sql.return_value = {
            "question": payload["question"],
            "sql": "SELECT revenue FROM financial_reports",
            "data": [{"revenue": 1_000_000}],
            "confidence": 0.95,
        }
        mock_service_cls.return_value = mock_service

        resp = client.post(
            "/api/v1/dify/tools/nl2sql",
            json=payload,
            headers={"X-API-Key": "tool-secret"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["data"][0]["revenue"] == 1_000_000
