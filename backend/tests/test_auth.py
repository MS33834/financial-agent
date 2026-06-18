"""认证相关测试."""

from fastapi.testclient import TestClient

from app.models.user import User


def test_login_success(client: TestClient, test_user: User) -> None:
    """测试登录成功."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": test_user.username, "password": "testpass"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient, test_user: User) -> None:
    """测试密码错误."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": test_user.username, "password": "wrongpass"},
    )
    assert response.status_code == 401


def test_get_me(client: TestClient, test_user: User, auth_headers: dict[str, str]) -> None:
    """测试获取当前用户信息."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == test_user.id
    assert data["username"] == test_user.username
