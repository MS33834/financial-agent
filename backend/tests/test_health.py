"""健康检查测试."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """测试健康检查接口."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "ok"


def test_readiness_check(client: TestClient) -> None:
    """测试就绪检查接口."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "ready"


def test_metrics_endpoint(client: TestClient) -> None:
    """测试 Prometheus 指标端点."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert b"process_" in response.content or b"fa_" in response.content
