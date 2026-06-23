"""真实 LLM 下的 Agent 复杂场景压力测试.

需要配置 OPENAI_API_KEY / OPENAI_BASE_URL / AGENT_LLM_MODEL 与 AGENT_INTENT_MODE=llm。
未配置时自动跳过，避免在 CI 中失败。
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent_runtime.graph import run_agent
from app.database import SessionLocal, get_db
from app.main import app
from app.models.financial_report import FinancialReport
from app.models.tenant import Tenant
from app.models.user import User
from app.security import create_access_token, get_password_hash

_SKIP_REAL_LLM = not os.environ.get("OPENAI_API_KEY")


@pytest.fixture
def e2e_db() -> Generator[Session, None, None]:
    """使用真实已提交会话，适用于跨请求断言."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def e2e_client(e2e_db: Session) -> Generator[TestClient, None, None]:
    """FastAPI 测试客户端，使用真实数据库会话."""

    def override_get_db() -> Generator[Session, None, None]:
        yield e2e_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _seed_report(db_session: Session, tenant: Tenant, **kwargs: Any) -> FinancialReport:
    """插入示例财报数据."""
    report = FinancialReport(
        tenant_id=tenant.id,
        year=kwargs.get("year", 2025),
        period=kwargs.get("period", "Q2"),
        revenue=kwargs.get("revenue", 10_000_000.0),
        net_profit=kwargs.get("net_profit", 1_500_000.0),
        total_assets=kwargs.get("total_assets", 50_000_000.0),
        total_liabilities=kwargs.get("total_liabilities", 20_000_000.0),
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


def _create_user(db_session: Session, tenant: Tenant, role: str = "admin") -> User:
    """创建测试用户."""
    import uuid

    username = f"llm-user-{uuid.uuid4().hex[:8]}"
    user = User(
        tenant_id=tenant.id,
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("testpass"),
        role=role,
        is_active="Y",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    """生成用户认证头."""
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}


def _setup_tenant_and_user(db: Session) -> tuple[Tenant, User]:
    """创建测试租户与用户."""
    import uuid

    tenant = Tenant(name="LLM Tenant", code=f"lt-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    user = _create_user(db, tenant)
    return tenant, user


@pytest.mark.skipif(_SKIP_REAL_LLM, reason="未配置 OPENAI_API_KEY，跳过真实 LLM 测试")
@pytest.mark.parametrize("_run_idx", range(3))
def test_real_llm_nl2sql_profit(e2e_db: Session, e2e_client: TestClient, _run_idx: int) -> None:
    """真实 LLM：查询净利润，多次运行验证稳定性."""
    tenant, user = _setup_tenant_and_user(e2e_db)
    _seed_report(e2e_db, tenant, year=2025, period="Q2", net_profit=3_200_000.0)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "2025年第二季度净利润是多少？"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "nl2sql"
    assert data["error"] is None
    assert "3200000" in data["answer"] or "3200000.0" in data["answer"]


@pytest.mark.skipif(_SKIP_REAL_LLM, reason="未配置 OPENAI_API_KEY，跳过真实 LLM 测试")
@pytest.mark.parametrize("_run_idx", range(3))
def test_real_llm_nl2sql_assets(e2e_db: Session, e2e_client: TestClient, _run_idx: int) -> None:
    """真实 LLM：查询总资产."""
    tenant, user = _setup_tenant_and_user(e2e_db)
    _seed_report(e2e_db, tenant, year=2025, period="Q2", total_assets=8_000_000.0)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "请查询2025年Q2的总资产情况"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "nl2sql"
    assert data["error"] is None
    assert "8000000" in data["answer"] or "8000000.0" in data["answer"]


@pytest.mark.skipif(_SKIP_REAL_LLM, reason="未配置 OPENAI_API_KEY，跳过真实 LLM 测试")
@pytest.mark.parametrize("_run_idx", range(3))
def test_real_llm_create_report(e2e_db: Session, e2e_client: TestClient, _run_idx: int) -> None:
    """真实 LLM：生成报告意图."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "帮我生成一份2025年第二季度的利润表报告"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "create_report"
    assert data["error"] is None
    assert data["tool_result"]["report_id"] is not None


@pytest.mark.skipif(_SKIP_REAL_LLM, reason="未配置 OPENAI_API_KEY，跳过真实 LLM 测试")
@pytest.mark.parametrize("_run_idx", range(3))
def test_real_llm_document_qa_no_docs(e2e_db: Session, e2e_client: TestClient, _run_idx: int) -> None:
    """真实 LLM：无文档时文档问答意图."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "请总结一下这份财务报表的核心内容"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "document_qa"
    assert "未找到" in data["answer"] or "请先上传" in data["answer"]


@pytest.mark.skipif(_SKIP_REAL_LLM, reason="未配置 OPENAI_API_KEY，跳过真实 LLM 测试")
@pytest.mark.parametrize("_run_idx", range(3))
def test_real_llm_unknown_intent(e2e_db: Session, e2e_client: TestClient, _run_idx: int) -> None:
    """真实 LLM：非财务问题应识别为 unknown."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "今天北京天气怎么样？适合穿什么衣服？"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "unknown"
    assert data["error"] is not None


@pytest.mark.skipif(_SKIP_REAL_LLM, reason="未配置 OPENAI_API_KEY，跳过真实 LLM 测试")
@pytest.mark.parametrize("_run_idx", range(3))
def test_real_llm_mixed_intent_priority(e2e_db: Session, e2e_client: TestClient, _run_idx: int) -> None:
    """真实 LLM：混合意图应优先报告."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "生成2025年Q2利润表，并顺便查询一下营业收入"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "create_report"


@pytest.mark.skipif(_SKIP_REAL_LLM, reason="未配置 OPENAI_API_KEY，跳过真实 LLM 测试")
def test_real_llm_run_agent_direct(e2e_db: Session) -> None:
    """真实 LLM：直接调用 run_agent 验证完整状态图."""
    tenant, user = _setup_tenant_and_user(e2e_db)
    _seed_report(e2e_db, tenant, year=2024, period="annual", net_profit=12_000_000.0)

    result = run_agent(
        question="2024年全年净利润是多少",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        db=e2e_db,
    )
    assert result["intent"] == "nl2sql"
    assert result["error"] is None
    assert "12000000" in result["answer"] or "12000000.0" in result["answer"]
