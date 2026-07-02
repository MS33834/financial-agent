"""错误自省路由（/api/v1/reflections）测试.

覆盖 list / get / resolve 三个端点，以及 401/403/404 处理。
"""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.error_reflection import ErrorReflection as Reflection
from app.models.tenant import Tenant
from app.models.user import User
from app.security import create_access_token, get_password_hash


def _admin(db: Session, tenant: Tenant, username: str = "admin-r") -> User:
    user = User(
        tenant_id=tenant.id,
        username=username,
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


def _reflection(
    db: Session, tenant: Tenant, **kwargs: object
) -> Reflection:
    defaults: dict[str, object] = {
        "tenant_id": tenant.id,
        "task_name": "document_parse",
        "task_id": "t-001",
        "resource_type": "document",
        "resource_id": "d-001",
        "exception_type": "ValueError",
        "exception_message": "bad input",
        "stack_trace": "Traceback ...",
        "error_category": "validation",
        "root_cause": "user input",
        "suggested_fix": "validate",
        "retried": 0,
        "resolved": False,
        "resolution": None,
    }
    defaults.update(kwargs)
    r = Reflection(**defaults)  # type: ignore[arg-type]
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_list_reflections_returns_tenant(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """应仅返回当前租户日志."""
    admin = _admin(db_session, test_tenant)
    _reflection(db_session, test_tenant)
    other = Tenant(name="O", code="o2")
    db_session.add(other)
    db_session.commit()
    _reflection(db_session, other)

    resp = client.get("/api/v1/reflections", headers=_admin_headers(admin))
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 1


def test_list_reflections_filters(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """category / resolved / resource_type 过滤参数应生效."""
    admin = _admin(db_session, test_tenant)
    _reflection(db_session, test_tenant, error_category="validation", resolved=False)
    _reflection(db_session, test_tenant, error_category="network", resolved=True)
    _reflection(db_session, test_tenant, error_category="validation", resolved=True, resource_type="report")

    resp = client.get(
        "/api/v1/reflections",
        params={"category": "validation", "resolved": "false"},
        headers=_admin_headers(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 1

    resp = client.get(
        "/api/v1/reflections",
        params={"resource_type": "report"},
        headers=_admin_headers(admin),
    )
    assert resp.json()["data"]["total"] == 1


def test_list_reflections_forbidden_for_viewer(
    client: TestClient, viewer_auth_headers: dict[str, str]
) -> None:
    resp = client.get("/api/v1/reflections", headers=viewer_auth_headers)
    assert resp.status_code == 403


def test_list_reflections_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/reflections")
    assert resp.status_code == 401


def test_get_reflection_success(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    admin = _admin(db_session, test_tenant)
    r = _reflection(db_session, test_tenant)
    resp = client.get(f"/api/v1/reflections/{r.id}", headers=_admin_headers(admin))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == r.id
    assert data["exception_type"] == "ValueError"


def test_get_reflection_not_found(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    admin = _admin(db_session, test_tenant)
    resp = client.get(
        "/api/v1/reflections/non-existent", headers=_admin_headers(admin)
    )
    assert resp.status_code == 404


def test_get_reflection_other_tenant_returns_404(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    admin = _admin(db_session, test_tenant)
    other = Tenant(name="O2", code="o3")
    db_session.add(other)
    db_session.commit()
    r = _reflection(db_session, other)
    resp = client.get(
        f"/api/v1/reflections/{r.id}", headers=_admin_headers(admin)
    )
    assert resp.status_code == 404


def test_resolve_reflection_success(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    admin = _admin(db_session, test_tenant)
    r = _reflection(db_session, test_tenant, resolved=False)
    resp = client.post(
        f"/api/v1/reflections/{r.id}/resolve",
        headers=_admin_headers(admin),
        json={"resolution": "已修正校验逻辑"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["resolved"] is True
    assert data["resolution"] == "已修正校验逻辑"

    db_session.refresh(r)
    assert r.resolved is True
    assert r.resolution == "已修正校验逻辑"


def test_resolve_reflection_not_found(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    admin = _admin(db_session, test_tenant)
    resp = client.post(
        "/api/v1/reflections/ghost/resolve",
        headers=_admin_headers(admin),
        json={"resolution": "x"},
    )
    assert resp.status_code == 404


def test_resolve_reflection_empty_resolution_rejected(
    client: TestClient, db_session: Session, test_tenant: Tenant
) -> None:
    """resolution 字段为空白应被 Pydantic 拒绝."""
    admin = _admin(db_session, test_tenant)
    r = _reflection(db_session, test_tenant)
    resp = client.post(
        f"/api/v1/reflections/{r.id}/resolve",
        headers=_admin_headers(admin),
        json={"resolution": ""},
    )
    assert resp.status_code == 422
