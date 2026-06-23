"""Agent 复杂场景与用户体验测试.

覆盖边界情况、降级策略、权限隔离、审计追踪等真实使用场景，
确保 Agent 在异常输入或依赖不可用时仍能给出合理响应。
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent_runtime.graph import run_agent
from app.database import SessionLocal, get_db
from app.llm import LLMUnavailableError
from app.main import app
from app.models.audit_log import AuditLog
from app.models.financial_report import FinancialReport
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate
from app.security import create_access_token, get_password_hash
from app.services.api_key_service import create_api_key


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
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


def _create_user(db_session: Session, tenant: Tenant, role: str = "admin") -> User:
    """创建测试用户."""
    username = f"agent-user-{uuid.uuid4().hex[:8]}"
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
    tenant = Tenant(name="Agent Tenant", code=f"at-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    user = _create_user(db, tenant)
    return tenant, user


def test_agent_missing_report_parameters(e2e_db: Session, e2e_client: TestClient) -> None:
    """报告意图但无法提取年份/周期时，Agent 仍应创建报告并给出提示."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "帮我生成一份利润表"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "create_report"
    assert "报告" in data["answer"]
    assert data["tool_result"]["report_id"] is not None


def test_agent_document_qa_without_documents(
    e2e_db: Session,
    e2e_client: TestClient,
) -> None:
    """租户下无可用文档时，document_qa 意图应优雅提示用户上传."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "总结一下这份文档讲了什么"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "document_qa"
    assert "未找到" in data["answer"] or "请先上传" in data["answer"]


def test_agent_parse_document_without_id(e2e_db: Session, e2e_client: TestClient) -> None:
    """解析文档意图但未提供 document_id 时，Agent 应返回明确错误."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "帮我解析一下刚上传的文件"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "parse_document"
    assert data["error"] is not None
    assert "document_id" in data["answer"] or "缺少" in data["answer"]


def test_agent_tool_execution_error_is_caught(
    e2e_db: Session,
    e2e_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """工具执行抛出异常时，Agent 应捕获并返回错误信息而非 500."""
    tenant, user = _setup_tenant_and_user(e2e_db)
    _seed_report(e2e_db, tenant, year=2025, period="Q2", net_profit=1_000_000.0)

    def _boom(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("模拟查询服务异常")

    monkeypatch.setattr("app.agent_runtime.tools.QueryService.nl2sql", _boom)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "2025年Q2净利润是多少"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "nl2sql"
    assert data["error"] is not None
    assert "工具执行失败" in data["answer"] or "处理失败" in data["answer"]


def test_agent_api_key_with_scope_can_chat(
    e2e_db: Session,
    e2e_client: TestClient,
) -> None:
    """具备 queries:nl2sql scope 的 API Key 应能调用 Agent."""
    tenant, user = _setup_tenant_and_user(e2e_db)
    _seed_report(e2e_db, tenant, year=2025, period="Q2", net_profit=2_000_000.0)

    api_key_record, plain_key = create_api_key(
        db=e2e_db,
        user=user,
        data=ApiKeyCreate(name="agent-test", scopes=["queries:nl2sql"]),
    )
    e2e_db.commit()

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers={"X-API-Key": plain_key},
        json={"question": "2025年Q2净利润是多少"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "nl2sql"
    assert "2000000" in data["answer"] or "2000000.0" in data["answer"]

    e2e_db.delete(api_key_record)
    e2e_db.commit()


def test_agent_api_key_without_scope_is_forbidden(
    e2e_db: Session,
    e2e_client: TestClient,
) -> None:
    """缺少 queries:nl2sql scope 的 API Key 应被拒绝访问 Agent."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    api_key_record, plain_key = create_api_key(
        db=e2e_db,
        user=user,
        data=ApiKeyCreate(name="agent-no-scope", scopes=["documents:read"]),
    )
    e2e_db.commit()

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers={"X-API-Key": plain_key},
        json={"question": "2025年Q2净利润是多少"},
    )
    assert response.status_code == 403

    e2e_db.delete(api_key_record)
    e2e_db.commit()


def test_agent_revoked_api_key_is_forbidden(
    e2e_db: Session,
    e2e_client: TestClient,
) -> None:
    """吊销的 API Key 不能调用 Agent."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    api_key_record, plain_key = create_api_key(
        db=e2e_db,
        user=user,
        data=ApiKeyCreate(name="agent-revoked", scopes=["queries:nl2sql"]),
    )
    api_key_record.is_active = "N"
    e2e_db.commit()

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers={"X-API-Key": plain_key},
        json={"question": "2025年Q2净利润是多少"},
    )
    assert response.status_code == 401

    e2e_db.delete(api_key_record)
    e2e_db.commit()


def test_agent_llm_mode_fallback_to_rule(
    e2e_db: Session,
    e2e_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """agent_intent_mode=llm 但 LLM 不可用时，应降级到规则意图识别."""
    tenant, user = _setup_tenant_and_user(e2e_db)
    _seed_report(e2e_db, tenant, year=2025, period="Q2", net_profit=3_000_000.0)

    # 强制节点认为当前处于 llm 模式，同时让 LLM 调用抛出不可用异常
    monkeypatch.setattr(
        "app.agent_runtime.nodes.get_settings",
        lambda: type("S", (), {"agent_intent_mode": "llm"})(),
    )

    def _raise_llm_unavailable(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise LLMUnavailableError("LLM 服务不可用")

    monkeypatch.setattr("app.agent_runtime.nodes.classify_intent_llm", _raise_llm_unavailable)
    monkeypatch.setattr("app.agent_runtime.nodes.extract_parameters_llm", _raise_llm_unavailable)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "2025年Q2净利润是多少"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "nl2sql"
    assert "3000000" in data["answer"] or "3000000.0" in data["answer"]


def test_agent_mixed_intent_priority(e2e_db: Session, e2e_client: TestClient) -> None:
    """混合意图问题应遵循报告 > 文档问答 > 文档解析 > 查询的优先级."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "生成 2025 Q2 利润表并查询营业收入"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "create_report"


def test_agent_chat_records_audit_log(
    e2e_db: Session,
    e2e_client: TestClient,
) -> None:
    """Agent 调用应在审计日志中记录 started 与 success/failed 事件."""
    tenant, user = _setup_tenant_and_user(e2e_db)
    _seed_report(e2e_db, tenant, year=2025, period="Q2", net_profit=4_000_000.0)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "2025年Q2净利润是多少"},
    )
    assert response.status_code == 200

    logs = (
        e2e_db.query(AuditLog)
        .filter(AuditLog.user_id == user.id, AuditLog.action == "agent.chat")
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    assert len(logs) >= 2
    results = {log.result for log in logs}
    assert "started" in results
    assert "success" in results


def test_agent_long_question_truncated_in_audit(
    e2e_db: Session,
    e2e_client: TestClient,
) -> None:
    """超长问题在审计日志 reason 中应被截断."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    long_question = "查询" + "2025年" * 200
    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": long_question},
    )
    assert response.status_code == 200

    log = (
        e2e_db.query(AuditLog)
        .filter(AuditLog.user_id == user.id, AuditLog.action == "agent.chat")
        .first()
    )
    assert log is not None
    assert len(log.reason) <= 250


def test_agent_unknown_intent_gives_friendly_response(
    e2e_db: Session,
    e2e_client: TestClient,
) -> None:
    """未知意图问题应返回友好提示而非异常."""
    _tenant, user = _setup_tenant_and_user(e2e_db)

    response = e2e_client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(user),
        json={"question": "今天北京天气怎么样"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "unknown"
    assert data["error"] is not None
    assert "无法识别" in data["answer"] or "财务" in data["answer"]


def test_agent_run_agent_state_transitions(e2e_db: Session) -> None:
    """直接调用 run_agent 验证 LangGraph 状态完整流转."""
    tenant, user = _setup_tenant_and_user(e2e_db)
    _seed_report(e2e_db, tenant, year=2025, period="Q2", net_profit=5_000_000.0)

    result = run_agent(
        question="2025年Q2净利润是多少",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        db=e2e_db,
    )
    assert result["intent"] == "nl2sql"
    assert result["error"] is None
    assert result["tool_result"] is not None
    assert "5000000" in result["answer"] or "5000000.0" in result["answer"]
