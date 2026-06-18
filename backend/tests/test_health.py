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
