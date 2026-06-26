"""健康检查路由补充测试.

补充 liveness、readiness 多依赖场景与响应结构校验，与 test_health.py 互为补充。
"""

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import app.routers.health as health_module


def test_liveness_check(client: TestClient) -> None:
    """存活探针应返回 alive."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "alive"


def test_live_does_not_invoke_dependency_checks(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    """存活探针不应触发依赖检查，即便依赖检查会抛错也应返回 200."""

    def _boom() -> tuple[bool, str]:
        raise RuntimeError("不应被调用")

    monkeypatch.setattr(health_module, "_check_database", _boom)
    monkeypatch.setattr(health_module, "_check_redis", _boom)
    monkeypatch.setattr(health_module, "_check_minio", _boom)

    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["message"] == "alive"


def test_readiness_all_dependencies_down(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """所有依赖均不可用时返回 503 且整体 not_ready."""
    monkeypatch.setattr(health_module, "_check_database", lambda: (False, "db down"))
    monkeypatch.setattr(health_module, "_check_redis", lambda: (False, "redis down"))
    monkeypatch.setattr(health_module, "_check_minio", lambda: (False, "minio down"))

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    for name in ("database", "redis", "minio"):
        assert data["dependencies"][name]["status"] == "down"


def test_readiness_minio_down_only(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """仅 MinIO 不可用时整体仍为 not_ready（503）."""
    monkeypatch.setattr(health_module, "_check_database", lambda: (True, "connected"))
    monkeypatch.setattr(health_module, "_check_redis", lambda: (True, "connected"))
    monkeypatch.setattr(health_module, "_check_minio", lambda: (False, "minio error"))

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["dependencies"]["database"]["status"] == "up"
    assert data["dependencies"]["redis"]["status"] == "up"
    assert data["dependencies"]["minio"]["status"] == "down"
    assert data["dependencies"]["minio"]["message"] == "minio error"


def test_readiness_latency_ms_is_numeric(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """每个依赖应返回非负 latency_ms."""
    monkeypatch.setattr(health_module, "_check_database", lambda: (True, "connected"))
    monkeypatch.setattr(health_module, "_check_redis", lambda: (True, "connected"))
    monkeypatch.setattr(health_module, "_check_minio", lambda: (True, "connected"))

    response = client.get("/health/ready")
    assert response.status_code == 200
    deps = response.json()["dependencies"]
    for name in ("database", "redis", "minio"):
        latency = deps[name]["latency_ms"]
        assert isinstance(latency, (int, float))
        assert latency >= 0


def test_readiness_response_structure(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """就绪探针响应应包含 status 与完整 dependencies 结构."""
    monkeypatch.setattr(health_module, "_check_database", lambda: (True, "connected"))
    monkeypatch.setattr(health_module, "_check_redis", lambda: (True, "connected"))
    monkeypatch.setattr(health_module, "_check_minio", lambda: (True, "connected"))

    response = client.get("/health/ready")
    data = response.json()
    assert data["status"] == "ready"
    assert set(data["dependencies"].keys()) == {"database", "redis", "minio"}
    for status_obj in data["dependencies"].values():
        assert "status" in status_obj
        assert "latency_ms" in status_obj
        assert "message" in status_obj


def test_readiness_database_down(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """数据库不可用时整体为 not_ready."""
    monkeypatch.setattr(health_module, "_check_database", lambda: (False, "db error"))
    monkeypatch.setattr(health_module, "_check_redis", lambda: (True, "connected"))
    monkeypatch.setattr(health_module, "_check_minio", lambda: (True, "connected"))

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["dependencies"]["database"]["status"] == "down"
    assert data["dependencies"]["database"]["message"] == "db error"


def test_health_check_response_model(client: TestClient) -> None:
    """健康检查响应应符合 BaseResponse 契约（code/message）."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) >= {"code", "message"}
    assert data["code"] == 0
