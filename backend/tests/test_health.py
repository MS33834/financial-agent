"""健康检查测试."""

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import app.routers.health as health_module


def test_health_check(client: TestClient) -> None:
    """测试健康检查接口."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "ok"


def test_readiness_check(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """测试就绪检查接口（mock 外部依赖，避免测试环境要求真实服务）."""
    monkeypatch.setattr(health_module, "_check_database", lambda: (True, "connected"))
    monkeypatch.setattr(health_module, "_check_redis", lambda: (True, "connected"))
    monkeypatch.setattr(health_module, "_check_minio", lambda: (True, "connected"))

    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["dependencies"]["database"]["status"] == "up"
    assert data["dependencies"]["redis"]["status"] == "up"
    assert data["dependencies"]["minio"]["status"] == "up"


def test_readiness_check_dependency_down(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """测试就绪检查在依赖异常时返回 503."""
    monkeypatch.setattr(health_module, "_check_database", lambda: (True, "connected"))
    monkeypatch.setattr(health_module, "_check_redis", lambda: (False, "connection refused"))
    monkeypatch.setattr(health_module, "_check_minio", lambda: (True, "connected"))

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["dependencies"]["redis"]["status"] == "down"


def test_metrics_endpoint(client: TestClient) -> None:
    """测试 Prometheus 指标端点."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert b"process_" in response.content or b"fa_" in response.content
