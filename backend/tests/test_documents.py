"""文档解析任务测试."""

import pytest
from fastapi.testclient import TestClient

from app.tasks.document_tasks import parse_document_task


def test_create_document_task(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建文档解析任务并触发异步任务."""
    delayed_ids: list[str] = []

    def fake_delay(document_id: str) -> None:
        delayed_ids.append(document_id)

    monkeypatch.setattr(parse_document_task, "delay", fake_delay)

    payload = {"filename": "profit_q2_2025.pdf", "storage_key": "docs/profit_q2_2025.pdf"}
    response = client.post("/api/v1/documents", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["filename"] == payload["filename"]
    assert data["status"] == "pending"
    assert len(delayed_ids) == 1
    assert data["id"] == delayed_ids[0]


def test_list_documents(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """测试文档列表分页."""
    # 先创建两个任务
    for i in range(2):
        client.post(
            "/api/v1/documents",
            json={"filename": f"doc{i}.pdf", "storage_key": f"docs/doc{i}.pdf"},
            headers=auth_headers,
        )

    response = client.get("/api/v1/documents?page=1&page_size=10", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_get_document_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """测试获取不存在的文档."""
    response = client.get("/api/v1/documents/non-existent-id", headers=auth_headers)
    assert response.status_code == 404
