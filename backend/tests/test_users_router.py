"""用户管理路由（/api/v1/users）测试.

覆盖列表 / 创建 / 更新 / 删除 / 重置密码 5 个端点，以及：
- 角色权限校验（仅管理员）
- 租户隔离（不能操作其他租户的用户）
- 唯一约束冲突（409）
- 自我删除保护（不能删自己）
"""

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User
from app.security import create_access_token, get_password_hash


def _admin_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}


def _create_user(
    db: Session,
    tenant: Tenant,
    username: str,
    role: str = "viewer",
    email: str | None = None,
) -> User:
    user = User(
        tenant_id=tenant.id,
        username=username,
        email=email or f"{username}@example.com",
        hashed_password=get_password_hash("initpass1"),
        role=role,
        is_active="Y",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_list_users_returns_tenant_users(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """应仅返回当前租户的用户."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    _create_user(db_session, test_tenant, "u1")
    _create_user(db_session, test_tenant, "u2")

    # 其他租户的用户不应出现在结果中
    other_tenant = Tenant(name="Other", code="other")
    db_session.add(other_tenant)
    db_session.commit()
    _create_user(db_session, other_tenant, "stranger")

    resp = client.get("/api/v1/users", headers=_admin_headers(admin))
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    usernames = {u["username"] for u in items}
    assert usernames == {"admin1", "u1", "u2"}


def test_list_users_forbidden_for_viewer(
    client: TestClient, viewer_auth_headers: dict[str, str]
) -> None:
    """viewer 角色无法访问用户列表."""
    resp = client.get("/api/v1/users", headers=viewer_auth_headers)
    assert resp.status_code == 403


def test_list_users_requires_auth(client: TestClient) -> None:
    """无 token 应返回 401."""
    resp = client.get("/api/v1/users")
    assert resp.status_code == 401


def test_create_user_success(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """管理员可创建新用户."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    resp = client.post(
        "/api/v1/users",
        headers=_admin_headers(admin),
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "secret123",
            "role": "viewer",
            "is_active": "Y",
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    # 真实写入了数据库
    created = db_session.query(User).filter(User.username == "newuser").first()
    assert created is not None
    assert created.tenant_id == test_tenant.id


def test_create_user_conflict_on_duplicate_username(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """同名用户应返回 409."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    _create_user(db_session, test_tenant, "duplicated")

    resp = client.post(
        "/api/v1/users",
        headers=_admin_headers(admin),
        json={"username": "duplicated", "password": "secret123"},
    )
    assert resp.status_code == 409
    assert "已存在" in resp.json()["detail"]


def test_create_user_handles_unexpected_integrity_error(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """非唯一约束的 IntegrityError 也应被 409 兜底（回归保护）."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")

    # 模拟 commit 时抛 IntegrityError（覆盖 rollback 路径）
    with client:
        from app.routers import users as users_router

        original_commit = users_router.User.__class__  # type: ignore[attr-defined]

        def _fake_commit(_self: object) -> None:
            raise IntegrityError("stmt", "params", "orig")

        # 实际是 db.commit() 抛错，直接对 Session monkey-patch
        from unittest.mock import patch

        with patch.object(db_session, "commit", side_effect=IntegrityError("s", "p", "o")):
            resp = client.post(
                "/api/v1/users",
                headers=_admin_headers(admin),
                json={"username": "boom", "password": "secret123"},
            )
    assert resp.status_code == 409


def test_create_user_forbidden_for_viewer(
    client: TestClient, db_session: Session, test_tenant: Tenant, viewer_auth_headers: dict[str, str]
) -> None:
    """viewer 不能创建用户."""
    resp = client.post(
        "/api/v1/users",
        headers=viewer_auth_headers,
        json={"username": "x", "password": "secret123"},
    )
    assert resp.status_code == 403


def test_update_user_updates_fields(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """PUT /users/{id} 可更新邮箱/角色/启用状态/密码."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    target = _create_user(db_session, test_tenant, "target")

    resp = client.put(
        f"/api/v1/users/{target.id}",
        headers=_admin_headers(admin),
        json={"email": "new@x.com", "role": "finance_manager", "is_active": "N"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["email"] == "new@x.com"
    assert data["role"] == "finance_manager"
    assert data["is_active"] == "N"

    db_session.refresh(target)
    assert target.email == "new@x.com"
    assert target.role == "finance_manager"
    assert target.is_active == "N"


def test_update_user_password(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """PUT /users/{id} 传入 password 应更新密码哈希."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    target = _create_user(db_session, test_tenant, "target")
    old_hash = target.hashed_password

    resp = client.put(
        f"/api/v1/users/{target.id}",
        headers=_admin_headers(admin),
        json={"password": "newsecret123"},
    )
    assert resp.status_code == 200
    db_session.refresh(target)
    assert target.hashed_password != old_hash


def test_update_user_not_found(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """更新不存在的用户应 404."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    resp = client.put(
        "/api/v1/users/non-existent-id",
        headers=_admin_headers(admin),
        json={"email": "x@y.com"},
    )
    assert resp.status_code == 404


def test_update_user_other_tenant_returns_404(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """跨租户更新应被 404 隔离（不暴露存在性）."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    other_tenant = Tenant(name="Other", code="other")
    db_session.add(other_tenant)
    db_session.commit()
    stranger = _create_user(db_session, other_tenant, "stranger")

    resp = client.put(
        f"/api/v1/users/{stranger.id}",
        headers=_admin_headers(admin),
        json={"email": "hijack@x.com"},
    )
    assert resp.status_code == 404


def test_delete_user_success(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """管理员可删除其他用户."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    target = _create_user(db_session, test_tenant, "to-delete")

    resp = client.delete(f"/api/v1/users/{target.id}", headers=_admin_headers(admin))
    assert resp.status_code == 204
    assert db_session.query(User).filter(User.id == target.id).first() is None


def test_delete_user_self_blocked(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """不能删除当前登录用户自身（防误锁）."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    resp = client.delete(f"/api/v1/users/{admin.id}", headers=_admin_headers(admin))
    assert resp.status_code == 400
    assert "当前登录用户" in resp.json()["detail"]


def test_delete_user_not_found(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """删除不存在的用户应 404."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    resp = client.delete("/api/v1/users/ghost", headers=_admin_headers(admin))
    assert resp.status_code == 404


def test_reset_password_success(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """重置密码应更新哈希."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    target = _create_user(db_session, test_tenant, "target")
    old_hash = target.hashed_password

    resp = client.post(
        f"/api/v1/users/{target.id}/reset-password",
        headers=_admin_headers(admin),
        json={"password": "fresh-secret-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == target.id
    assert resp.json()["data"]["reset"] is True

    db_session.refresh(target)
    assert target.hashed_password != old_hash


def test_reset_password_not_found(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """重置不存在的用户密码应 404."""
    admin = _create_user(db_session, test_tenant, "admin1", role="admin")
    resp = client.post(
        "/api/v1/users/ghost/reset-password",
        headers=_admin_headers(admin),
        json={"password": "whatever123"},
    )
    assert resp.status_code == 404


def test_reset_password_forbidden_for_viewer(
    client: TestClient, db_session: Session, test_tenant: Tenant, viewer_auth_headers: dict[str, str]
) -> None:
    """viewer 不能重置其他用户密码."""
    target = _create_user(db_session, test_tenant, "target")
    resp = client.post(
        f"/api/v1/users/{target.id}/reset-password",
        headers=viewer_auth_headers,
        json={"password": "whatever123"},
    )
    assert resp.status_code == 403
