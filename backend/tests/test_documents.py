"""文档解析任务测试."""

from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.tenant import Tenant
from app.models.user import User
from app.security import create_access_token, get_password_hash
from app.tasks.document_tasks import parse_document_task


class FakeStorageClient:
    """测试用对象存储客户端."""

    def __init__(self, stored: dict[str, bytes] | None = None) -> None:
        """初始化."""
        self.stored = stored or {}
        self.uploaded: list[dict[str, Any]] = []

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """模拟上传."""
        self.stored[key] = data
        self.uploaded.append(
            {"key": key, "data": data, "content_type": content_type, "metadata": metadata}
        )
        return f"http://fake-minio/financial-agent/{key}"

    def download_bytes(self, key: str) -> bytes:
        """模拟下载."""
        if key not in self.stored:
            raise RuntimeError(f"Object {key} not found")
        return self.stored[key]


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


def test_viewer_cannot_upload(
    client: TestClient,
    viewer_auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 viewer 角色无法上传文档."""
    monkeypatch.setattr("app.routers.documents.get_storage_client", lambda: FakeStorageClient())
    monkeypatch.setattr(parse_document_task, "delay", lambda _document_id: None)

    csv_content = b"year,period,revenue\n2025,Q2,10000000\n"
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("profit_2025_q2.csv", BytesIO(csv_content), "text/csv")},
        headers=viewer_auth_headers,
    )
    assert response.status_code == 403


def test_upload_document(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试文件上传并创建解析任务."""
    fake_storage = FakeStorageClient()
    monkeypatch.setattr("app.routers.documents.get_storage_client", lambda: fake_storage)
    monkeypatch.setattr(parse_document_task, "delay", lambda _document_id: None)

    csv_content = b"year,period,revenue\n2025,Q2,10000000\n"
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("profit_2025_q2.csv", BytesIO(csv_content), "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["filename"] == "profit_2025_q2.csv"
    assert data["status"] == "pending"
    assert len(fake_storage.uploaded) == 1
    assert fake_storage.uploaded[0]["content_type"] == "text/csv"


def test_document_list_filter_by_status(
    client: TestClient,
    db_session: Session,
) -> None:
    """测试按状态筛选文档列表."""
    tenant = Tenant(name="Filter Tenant", code="filter")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        username="filteruser",
        email="filter@example.com",
        hashed_password=get_password_hash("testpass"),
        role="admin",
        is_active="Y",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doc_success = Document(
        tenant_id=tenant.id,
        created_by=user.id,
        filename="success_doc.pdf",
        storage_key="docs/success_doc.pdf",
        status="success",
    )
    doc_review = Document(
        tenant_id=tenant.id,
        created_by=user.id,
        filename="review_doc.pdf",
        storage_key="docs/review_doc.pdf",
        status="needs_review",
    )
    db_session.add_all([doc_success, doc_review])
    db_session.commit()

    token = {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}

    response = client.get("/api/v1/documents?status=success", headers=token)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "success"

    response = client.get("/api/v1/documents?status=needs_review", headers=token)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "needs_review"

    response = client.get("/api/v1/documents", headers=token)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 2
