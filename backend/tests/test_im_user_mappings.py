"""IM 用户映射管理接口测试."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.im_user_mapping import IMUserMapping
from app.models.tenant import Tenant
from app.models.user import User
from app.security import get_password_hash


def _create_admin_user(db_session: Session) -> tuple[User, dict[str, str], Tenant]:
    """创建管理员用户并返回用户、认证头和租户."""
    tenant = Tenant(name="IM Mapping Test", code="im-mapping-test")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        username="admin",
        hashed_password=get_password_hash("pass"),
        role="admin",
        is_active="Y",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    from app.security import create_access_token

    token = create_access_token({"sub": user.id})
    return user, {"Authorization": f"Bearer {token}"}, tenant


def test_list_im_user_mappings(db_session: Session, client: TestClient) -> None:
    """管理员可查看映射列表."""
    user, headers, tenant = _create_admin_user(db_session)
    mapping = IMUserMapping(
        tenant_id=tenant.id,
        user_id=user.id,
        platform="dingtalk",
        im_user_id="ding_001",
    )
    db_session.add(mapping)
    db_session.commit()

    resp = client.get("/api/v1/im-user-mappings", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["im_user_id"] == "ding_001"


def test_list_im_user_mappings_filter_by_platform(
    db_session: Session, client: TestClient
) -> None:
    """按平台筛选映射列表."""
    user, headers, tenant = _create_admin_user(db_session)
    db_session.add_all(
        [
            IMUserMapping(
                tenant_id=tenant.id,
                user_id=user.id,
                platform="dingtalk",
                im_user_id="ding_001",
            ),
            IMUserMapping(
                tenant_id=tenant.id,
                user_id=user.id,
                platform="feishu",
                im_user_id="fs_001",
            ),
        ]
    )
    db_session.commit()

    resp = client.get("/api/v1/im-user-mappings?platform=feishu", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["platform"] == "feishu"


def test_create_im_user_mapping(db_session: Session, client: TestClient) -> None:
    """管理员可创建映射."""
    user, headers, _tenant = _create_admin_user(db_session)

    resp = client.post(
        "/api/v1/im-user-mappings",
        json={"user_id": user.id, "platform": "wecom", "im_user_id": "wx_001"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["platform"] == "wecom"
    assert resp.json()["im_user_id"] == "wx_001"


def test_create_im_user_mapping_duplicate(
    db_session: Session, client: TestClient
) -> None:
    """重复创建同一平台同一 IM 用户会冲突."""
    user, headers, tenant = _create_admin_user(db_session)
    db_session.add(
        IMUserMapping(
            tenant_id=tenant.id,
            user_id=user.id,
            platform="dingtalk",
            im_user_id="ding_001",
        )
    )
    db_session.commit()

    resp = client.post(
        "/api/v1/im-user-mappings",
        json={"user_id": user.id, "platform": "dingtalk", "im_user_id": "ding_001"},
        headers=headers,
    )
    assert resp.status_code == 409


def test_create_im_user_mapping_user_not_found(
    db_session: Session, client: TestClient
) -> None:
    """映射到不存在的用户会 404."""
    _user, headers, _tenant = _create_admin_user(db_session)

    resp = client.post(
        "/api/v1/im-user-mappings",
        json={"user_id": "non-existent", "platform": "dingtalk", "im_user_id": "x"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_create_im_user_mapping_missing_fields(
    db_session: Session, client: TestClient
) -> None:
    """缺少必填字段返回 400."""
    _user, headers, _tenant = _create_admin_user(db_session)

    resp = client.post(
        "/api/v1/im-user-mappings",
        json={"platform": "dingtalk"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_delete_im_user_mapping(db_session: Session, client: TestClient) -> None:
    """管理员可删除映射."""
    user, headers, tenant = _create_admin_user(db_session)
    mapping = IMUserMapping(
        tenant_id=tenant.id,
        user_id=user.id,
        platform="dingtalk",
        im_user_id="ding_001",
    )
    db_session.add(mapping)
    db_session.commit()
    db_session.refresh(mapping)

    resp = client.delete(f"/api/v1/im-user-mappings/{mapping.id}", headers=headers)
    assert resp.status_code == 204

    assert db_session.query(IMUserMapping).filter(IMUserMapping.id == mapping.id).first() is None


def test_delete_im_user_mapping_not_found(
    db_session: Session, client: TestClient
) -> None:
    """删除不存在的映射返回 404."""
    _user, headers, _tenant = _create_admin_user(db_session)

    resp = client.delete("/api/v1/im-user-mappings/non-existent", headers=headers)
    assert resp.status_code == 404


def test_im_user_mappings_forbidden_for_viewer(
    client: TestClient,
    viewer_auth_headers: dict[str, Any],
) -> None:
    """viewer 无权访问映射管理接口."""
    resp = client.get("/api/v1/im-user-mappings", headers=viewer_auth_headers)
    assert resp.status_code == 403
