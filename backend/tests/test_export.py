"""报告导出功能测试."""

from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.report import Report
from app.tasks.report_tasks import generate_report_task


class FakeStorageClient:
    """用于测试的假对象存储客户端."""

    def __init__(self) -> None:
        """初始化上传记录."""
        self.uploaded: list[dict[str, Any]] = []

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """模拟上传并返回固定 URL."""
        self.uploaded.append(
            {
                "key": key,
                "data": data,
                "content_type": content_type,
                "metadata": metadata,
            }
        )
        return f"http://fake-minio/financial-agent/{key}"


def _create_reviewing_report(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    """创建报告并手动置为 reviewing 状态."""
    monkeypatch.setattr(generate_report_task, "delay", lambda _report_id: None)

    response = client.post(
        "/api/v1/reports",
        json={
            "title": "导出测试报告",
            "report_type": "profit",
            "parameters": {"year": 2025, "period": "Q2"},
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    report_id = cast(str, response.json()["data"]["id"])

    report = db_session.query(Report).filter(Report.id == report_id).first()
    assert report is not None
    report.status = "reviewing"
    report.content = {
        "title": "2025年第二季度利润表",
        "summary": "2025年第二季度，公司实现营业收入 10000000.00 元。",
        "sections": [
            {"name": "营业收入", "metric": "revenue", "value": 10000000.0},
        ],
    }
    report.summary = report.content["summary"]
    db_session.commit()
    return report_id


def test_export_report_markdown(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试导出 Markdown 格式."""
    fake_storage = FakeStorageClient()
    monkeypatch.setattr(
        "app.routers.reports.get_storage_client",
        lambda: fake_storage,
    )

    report_id = _create_reviewing_report(client, auth_headers, db_session, monkeypatch)

    response = client.post(
        f"/api/v1/reports/{report_id}/export?format=markdown",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["format"] == "markdown"
    assert data["content_url"].endswith("/report.md")
    assert len(fake_storage.uploaded) == 1
    assert fake_storage.uploaded[0]["content_type"] == "text/markdown; charset=utf-8"


def test_export_report_json(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试导出 JSON 格式."""
    fake_storage = FakeStorageClient()
    monkeypatch.setattr(
        "app.routers.reports.get_storage_client",
        lambda: fake_storage,
    )

    report_id = _create_reviewing_report(client, auth_headers, db_session, monkeypatch)

    response = client.post(
        f"/api/v1/reports/{report_id}/export?format=json",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["format"] == "json"
    assert data["content_url"].endswith("/report.json")


def test_export_report_pdf(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试导出 PDF 格式."""
    fake_storage = FakeStorageClient()
    monkeypatch.setattr(
        "app.routers.reports.get_storage_client",
        lambda: fake_storage,
    )

    report_id = _create_reviewing_report(client, auth_headers, db_session, monkeypatch)

    response = client.post(
        f"/api/v1/reports/{report_id}/export?format=pdf",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["format"] == "pdf"
    assert data["content_url"].endswith("/report.pdf")
    assert len(fake_storage.uploaded) == 1
    assert fake_storage.uploaded[0]["content_type"] == "application/pdf"
    assert fake_storage.uploaded[0]["data"].startswith(b"%PDF")


def test_export_report_xlsx(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试导出 Excel 格式."""
    fake_storage = FakeStorageClient()
    monkeypatch.setattr(
        "app.routers.reports.get_storage_client",
        lambda: fake_storage,
    )

    report_id = _create_reviewing_report(client, auth_headers, db_session, monkeypatch)

    response = client.post(
        f"/api/v1/reports/{report_id}/export?format=xlsx",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["format"] == "xlsx"
    assert data["content_url"].endswith("/report.xlsx")
    assert len(fake_storage.uploaded) == 1
    assert fake_storage.uploaded[0]["content_type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert fake_storage.uploaded[0]["data"].startswith(b"PK")


def test_export_report_invalid_format(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试不支持的导出格式返回 400."""
    monkeypatch.setattr(
        "app.routers.reports.get_storage_client",
        lambda: FakeStorageClient(),
    )

    report_id = _create_reviewing_report(client, auth_headers, db_session, monkeypatch)

    response = client.post(
        f"/api/v1/reports/{report_id}/export?format=txt",
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_export_report_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """测试导出不存在的报告返回 404."""
    response = client.post(
        "/api/v1/reports/non-existent-id/export",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_export_report_wrong_status(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试非 reviewing/approved 状态不可导出."""
    monkeypatch.setattr(generate_report_task, "delay", lambda _report_id: None)
    monkeypatch.setattr(
        "app.routers.reports.get_storage_client",
        lambda: FakeStorageClient(),
    )

    response = client.post(
        "/api/v1/reports",
        json={"title": "未生成报告", "report_type": "cash"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    report_id = cast(str, response.json()["data"]["id"])

    response = client.post(
        f"/api/v1/reports/{report_id}/export",
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_viewer_cannot_export(
    client: TestClient,
    auth_headers: dict[str, str],
    viewer_auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 viewer 角色无法导出报告."""
    fake_storage = FakeStorageClient()
    monkeypatch.setattr("app.routers.reports.get_storage_client", lambda: fake_storage)

    report_id = _create_reviewing_report(client, auth_headers, db_session, monkeypatch)

    response = client.post(
        f"/api/v1/reports/{report_id}/export",
        headers=viewer_auth_headers,
    )
    assert response.status_code == 403
