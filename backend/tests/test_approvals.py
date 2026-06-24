"""人工审核相关测试."""

from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.report import Report
from app.tasks.report_tasks import generate_report_task


def _create_report(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    """辅助函数：创建报告并返回 ID（禁用异步生成任务）."""
    monkeypatch.setattr(generate_report_task, "delay", lambda _report_id: None)

    response = client.post(
        "/api/v1/reports",
        json={"title": "审核测试报告", "report_type": "cash"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data: dict[str, Any] = response.json()["data"]
    return cast(str, data["id"])


def _force_reviewing(db_session: Session, report_id: str) -> None:
    """将报告状态置为 reviewing，用于模拟异步生成完成."""
    report = db_session.query(Report).filter(Report.id == report_id).first()
    assert report is not None
    report.status = "reviewing"
    db_session.commit()


def test_approve_report(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试通过审核."""
    report_id = _create_report(client, auth_headers, monkeypatch)
    _force_reviewing(db_session, report_id)

    response = client.post(
        f"/api/v1/approvals/{report_id}/action",
        json={"action": "approve", "comments": "同意发布"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["report_id"] == report_id
    assert data["action"] == "approve"
    assert data["id"] is not None

    report_response = client.get(f"/api/v1/reports/{report_id}", headers=auth_headers)
    assert report_response.json()["data"]["status"] == "approved"


def test_reject_report(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试驳回审核."""
    report_id = _create_report(client, auth_headers, monkeypatch)
    _force_reviewing(db_session, report_id)

    response = client.post(
        f"/api/v1/approvals/{report_id}/action",
        json={"action": "reject", "comments": "数据有误"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["action"] == "reject"


def test_modify_report(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试退回修改."""
    report_id = _create_report(client, auth_headers, monkeypatch)
    _force_reviewing(db_session, report_id)

    response = client.post(
        f"/api/v1/approvals/{report_id}/action",
        json={"action": "modify", "comments": "请修改"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["action"] == "modify"

    report_response = client.get(f"/api/v1/reports/{report_id}", headers=auth_headers)
    assert report_response.json()["data"]["status"] == "draft"


def test_approve_invalid_action(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试非法审核操作.

    非法 action 值在 Schema 层被 Literal 枚举拦截，返回 422 校验错误。
    """
    report_id = _create_report(client, auth_headers, monkeypatch)
    _force_reviewing(db_session, report_id)

    response = client.post(
        f"/api/v1/approvals/{report_id}/action",
        json={"action": "freeze"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_approve_report_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """测试对不存在的报告进行审核."""
    response = client.post(
        "/api/v1/approvals/non-existent-id/action",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_approve_non_reviewing_report(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试对非 reviewing 状态的报告审核应返回 400."""
    monkeypatch.setattr(generate_report_task, "delay", lambda _report_id: None)

    response = client.post(
        "/api/v1/reports",
        json={"title": "未生成报告", "report_type": "cash"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    report_id = response.json()["data"]["id"]

    response = client.post(
        f"/api/v1/approvals/{report_id}/action",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_viewer_cannot_approve(
    client: TestClient,
    auth_headers: dict[str, str],
    viewer_auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 viewer 角色无法执行审核."""
    report_id = _create_report(client, auth_headers, monkeypatch)
    _force_reviewing(db_session, report_id)

    response = client.post(
        f"/api/v1/approvals/{report_id}/action",
        json={"action": "approve"},
        headers=viewer_auth_headers,
    )
    assert response.status_code == 403


def test_list_approvals(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试查询审核记录列表."""
    report_id = _create_report(client, auth_headers, monkeypatch)
    _force_reviewing(db_session, report_id)

    client.post(
        f"/api/v1/approvals/{report_id}/action",
        json={"action": "approve", "comments": "同意"},
        headers=auth_headers,
    )

    response = client.get("/api/v1/approvals", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1
    assert data[0]["report_id"] == report_id
    assert data[0]["action"] == "approve"

    filtered = client.get(f"/api/v1/approvals?report_id={report_id}", headers=auth_headers)
    assert filtered.status_code == 200
    assert len(filtered.json()["data"]) == 1
