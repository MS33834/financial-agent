"""ABAC 策略管理路由（/api/v1/access-policies）测试.

覆盖 list / create / update / delete 四个端点，覆盖：
- 任意登录用户可列出本租户策略
- 仅管理员可创建/修改/删除
- 跨租户隔离
- 404 处理
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.access_policy import AccessPolicy
from app.models.tenant import Tenant
from app.models.user import User
from app.security import create_access_token, get_password_hash


def _admin(db: Session, tenant: Tenant) -> User:
    user = User(
        tenant_id=tenant.id,
        username=f"admin-{tenant.code}",
        email=f"admin-{tenant.code}@example.com",
        hashed_password=get_password_hash("initpass1"),
        role="admin",
        is_active="Y",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _admin_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}


def _viewer(db: Session, tenant: Tenant) -> User:
    user = User(
        tenant_id=tenant.id,
        username=f"viewer-{tenant.code}",
        hashed_password=get_password_hash("initpass1"),
        role="viewer",
        is_active="Y",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _grant_abac_read(
    db: Session, tenant: Tenant, role: str = "admin"
) -> None:
    """为本租户添加 access_policy:read 允许策略，便于列表接口通过 ABAC 校验."""
    db.add(
        AccessPolicy(
            tenant_id=tenant.id,
            name=f"allow-{role}-to-read",
            resource_type="access_policy",
            action="read",
            effect="allow",
            priority=1,
            conditions={"user.role": role},
            is_active=True,
        )
    )
    db.commit()


def test_list_policies_returns_tenant_scoped(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """GET 应仅返回当前租户策略，按 priority 升序."""
    admin = _admin(db_session, test_tenant)
    _grant_abac_read(db_session, test_tenant)
    other = Tenant(name="Other", code="other")
    db_session.add(other)
    db_session.commit()

    mine = AccessPolicy(
        tenant_id=test_tenant.id,
        name="mine-allow",
        resource_type="report",
        action="read",
        effect="allow",
        priority=10,
        conditions={},
        is_active=True,
    )
    db_session.add(mine)
    stranger = AccessPolicy(
        tenant_id=other.id,
        name="stranger-deny",
        resource_type="report",
        action="read",
        effect="deny",
        priority=99,
        conditions={},
        is_active=True,
    )
    db_session.add(stranger)
    db_session.commit()

    resp = client.get("/api/v1/access-policies", headers=_admin_headers(admin))
    assert resp.status_code == 200
    payload = resp.json()["data"]
    items = payload["items"]
    # 1 个 abac helper + 1 个业务策略 = 2
    assert payload["total"] == 2
    names = {item["name"] for item in items}
    assert names == {"allow-admin-to-read", "mine-allow"}


def test_list_policies_orders_by_priority(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """多个策略应按 priority 升序返回."""
    admin = _admin(db_session, test_tenant)
    _grant_abac_read(db_session, test_tenant)
    for p, name in [(30, "mid"), (10, "top"), (50, "low")]:
        db_session.add(
            AccessPolicy(
                tenant_id=test_tenant.id,
                name=name,
                resource_type="report",
                action="read",
                effect="allow",
                priority=p,
                conditions={},
                is_active=True,
            )
        )
    db_session.commit()

    resp = client.get("/api/v1/access-policies", headers=_admin_headers(admin))
    items = resp.json()["data"]["items"]
    # abac helper 优先级 1 排在最前，业务策略按 priority 升序
    names = [item["name"] for item in items]
    assert names[0] == "allow-admin-to-read"
    assert names[1:] == ["top", "mid", "low"]


def test_list_policies_paginates(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """分页参数应被尊重."""
    admin = _admin(db_session, test_tenant)
    _grant_abac_read(db_session, test_tenant)
    for i in range(3):
        db_session.add(
            AccessPolicy(
                tenant_id=test_tenant.id,
                name=f"p{i}",
                resource_type="report",
                action="read",
                effect="allow",
                priority=i,
                conditions={},
                is_active=True,
            )
        )
    db_session.commit()

    resp = client.get(
        "/api/v1/access-policies",
        params={"page": 1, "page_size": 4},
        headers=_admin_headers(admin),
    )
    payload = resp.json()["data"]
    # abac helper + 3 业务策略 = 4
    assert payload["total"] == 4
    assert payload["page_size"] == 4
    assert len(payload["items"]) == 4


def test_list_policies_forbidden_without_auth(client: TestClient) -> None:
    """无 token 应 401."""
    resp = client.get("/api/v1/access-policies")
    assert resp.status_code == 401


def test_create_policy_success(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """管理员可创建策略."""
    admin = _admin(db_session, test_tenant)
    resp = client.post(
        "/api/v1/access-policies",
        headers=_admin_headers(admin),
        json={
            "name": "report-approve-only-admin",
            "resource_type": "report",
            "action": "approve",
            "effect": "allow",
            "priority": 5,
            "conditions": {"role": "admin"},
            "description": "only admin can approve",
            "is_active": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "report-approve-only-admin"
    assert data["tenant_id"] == test_tenant.id
    assert data["conditions"] == {"role": "admin"}


def test_create_policy_forbidden_for_viewer(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """viewer 无权创建策略."""
    viewer = _viewer(db_session, test_tenant)
    resp = client.post(
        "/api/v1/access-policies",
        headers=_admin_headers(viewer),
        json={
            "name": "x",
            "resource_type": "report",
            "action": "read",
            "effect": "allow",
        },
    )
    assert resp.status_code == 403


def test_update_policy_success(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """管理员可更新策略字段."""
    admin = _admin(db_session, test_tenant)
    policy = AccessPolicy(
        tenant_id=test_tenant.id,
        name="to-update",
        resource_type="report",
        action="read",
        effect="allow",
        priority=10,
        conditions={},
        is_active=True,
    )
    db_session.add(policy)
    db_session.commit()
    db_session.refresh(policy)

    resp = client.put(
        f"/api/v1/access-policies/{policy.id}",
        headers=_admin_headers(admin),
        json={"priority": 99, "is_active": False, "description": "deprecated"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["priority"] == 99
    assert data["is_active"] is False
    assert data["description"] == "deprecated"

    db_session.refresh(policy)
    assert policy.priority == 99
    assert policy.is_active is False


def test_update_policy_not_found(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """不存在的策略应 404."""
    admin = _admin(db_session, test_tenant)
    resp = client.put(
        "/api/v1/access-policies/non-existent",
        headers=_admin_headers(admin),
        json={"priority": 1},
    )
    assert resp.status_code == 404


def test_update_policy_other_tenant_returns_404(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """跨租户更新应被 404 隔离."""
    admin = _admin(db_session, test_tenant)
    other = Tenant(name="Other2", code="other2")
    db_session.add(other)
    db_session.commit()
    stranger = AccessPolicy(
        tenant_id=other.id,
        name="stranger",
        resource_type="report",
        action="read",
        effect="allow",
        priority=1,
        conditions={},
        is_active=True,
    )
    db_session.add(stranger)
    db_session.commit()

    resp = client.put(
        f"/api/v1/access-policies/{stranger.id}",
        headers=_admin_headers(admin),
        json={"priority": 999},
    )
    assert resp.status_code == 404


def test_delete_policy_success(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """管理员可删除策略."""
    admin = _admin(db_session, test_tenant)
    policy = AccessPolicy(
        tenant_id=test_tenant.id,
        name="to-delete",
        resource_type="report",
        action="read",
        effect="allow",
        priority=1,
        conditions={},
        is_active=True,
    )
    db_session.add(policy)
    db_session.commit()
    db_session.refresh(policy)

    resp = client.delete(
        f"/api/v1/access-policies/{policy.id}", headers=_admin_headers(admin)
    )
    assert resp.status_code == 204
    assert (
        db_session.query(AccessPolicy).filter(AccessPolicy.id == policy.id).first()
        is None
    )


def test_delete_policy_not_found(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """删除不存在的策略应 404."""
    admin = _admin(db_session, test_tenant)
    resp = client.delete(
        "/api/v1/access-policies/ghost", headers=_admin_headers(admin)
    )
    assert resp.status_code == 404


def test_delete_policy_forbidden_for_viewer(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """viewer 无权删除策略."""
    viewer = _viewer(db_session, test_tenant)
    policy = AccessPolicy(
        tenant_id=test_tenant.id,
        name="keep",
        resource_type="report",
        action="read",
        effect="allow",
        priority=1,
        conditions={},
        is_active=True,
    )
    db_session.add(policy)
    db_session.commit()
    db_session.refresh(policy)

    resp = client.delete(
        f"/api/v1/access-policies/{policy.id}", headers=_admin_headers(viewer)
    )
    assert resp.status_code == 403
