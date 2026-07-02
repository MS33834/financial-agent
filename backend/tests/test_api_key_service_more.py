"""API Key 业务服务（app.services.api_key_service）补全测试.

覆盖：
- generate_api_key / create_api_key 的明文返回与哈希存储
- list_api_keys / get_api_key_by_id / rotate_api_key / delete_api_key / revoke_api_key 的 CRUD 行为
- validate_api_key / get_api_key_owner 的认证校验（禁用、过期、错误、统计更新）
- 跨租户隔离
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate
from app.schemas.common import PaginationParams
from app.security import get_password_hash
from app.services.api_key_service import (
    API_KEY_PREFIX,
    create_api_key,
    delete_api_key,
    generate_api_key,
    get_api_key_by_id,
    get_api_key_owner,
    list_api_keys,
    revoke_api_key,
    rotate_api_key,
    validate_api_key,
)


def _tenant(db: Session, code: str = "t1") -> Tenant:
    t = Tenant(name="T-" + code, code=code)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _user(db: Session, tenant: Tenant, username: str = "u1") -> User:
    u = User(
        tenant_id=tenant.id,
        username=username,
        hashed_password=get_password_hash("initpass1"),
        role="admin",
        is_active="Y",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _pag(page: int = 1, size: int = 20) -> PaginationParams:
    return PaginationParams(page=page, page_size=size)


# ------------------------------------------------------------------
# generate_api_key
# ------------------------------------------------------------------


def test_generate_api_key_format() -> None:
    """生成的 key 应以 fa_ 开头，且长度 > 50."""
    key = generate_api_key()
    assert key.startswith(API_KEY_PREFIX)
    assert len(key) > 50


def test_generate_api_key_uniqueness() -> None:
    """连续生成两个 key 应不同."""
    assert generate_api_key() != generate_api_key()


# ------------------------------------------------------------------
# create_api_key
# ------------------------------------------------------------------


def test_create_api_key_returns_plain_once(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    record, plain = create_api_key(
        db_session, user, ApiKeyCreate(name="my-key", scopes=["read:report"])
    )
    assert record.name == "my-key"
    assert record.tenant_id == test_tenant.id
    assert record.user_id == user.id
    assert record.scopes == ["read:report"]
    assert record.is_active == "Y"
    assert plain.startswith(API_KEY_PREFIX)
    # db 中存的是哈希
    assert plain not in (record.key_hash,)
    assert len(record.key_hash) == 64  # SHA-256 hex


def test_create_api_key_uses_default_empty_scopes(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    record, _ = create_api_key(db_session, user, ApiKeyCreate(name="k"))
    assert record.scopes == []


def test_create_api_key_with_expiry(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    future = datetime.now(UTC) + timedelta(days=7)
    record, _ = create_api_key(
        db_session, user, ApiKeyCreate(name="k", expires_at=future)
    )
    assert record.expires_at is not None


# ------------------------------------------------------------------
# list_api_keys
# ------------------------------------------------------------------


def test_list_api_keys_returns_tenant_scoped(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant, "u1")
    create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    create_api_key(db_session, user, ApiKeyCreate(name="k2"))

    other = _tenant(db_session, "o")
    other_user = _user(db_session, other, "stranger")
    create_api_key(db_session, other_user, ApiKeyCreate(name="x"))

    result = list_api_keys(
        db_session, tenant_id=test_tenant.id, pagination=_pag()
    )
    assert result["total"] == 2
    assert {it["name"] for it in result["items"]} == {"k1", "k2"}


def test_list_api_keys_pagination(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant, "u1")
    for i in range(5):
        create_api_key(db_session, user, ApiKeyCreate(name=f"k{i}"))

    result = list_api_keys(
        db_session, tenant_id=test_tenant.id, pagination=_pag(page=2, size=2)
    )
    assert result["total"] == 5
    assert len(result["items"]) == 2
    assert result["page"] == 2
    assert result["page_size"] == 2


def test_list_api_keys_empty(
    db_session: Session, test_tenant: Tenant
) -> None:
    result = list_api_keys(
        db_session, tenant_id=test_tenant.id, pagination=_pag()
    )
    assert result["total"] == 0
    assert result["items"] == []


# ------------------------------------------------------------------
# get_api_key_by_id
# ------------------------------------------------------------------


def test_get_api_key_by_id_found(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    record, _ = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    found = get_api_key_by_id(db_session, key_id=record.id, tenant_id=test_tenant.id)
    assert found is not None
    assert found.id == record.id


def test_get_api_key_by_id_not_found(
    db_session: Session, test_tenant: Tenant
) -> None:
    assert get_api_key_by_id(
        db_session, key_id="ghost", tenant_id=test_tenant.id
    ) is None


def test_get_api_key_by_id_other_tenant_returns_none(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    record, _ = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    other = _tenant(db_session, "o2")
    assert (
        get_api_key_by_id(db_session, key_id=record.id, tenant_id=other.id)
        is None
    )


# ------------------------------------------------------------------
# rotate_api_key
# ------------------------------------------------------------------


def test_rotate_api_key_returns_new_plain(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    record, old_plain = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    old_hash = record.key_hash

    new_record, new_plain = rotate_api_key(
        db_session, key_id=record.id, tenant_id=test_tenant.id
    )
    assert new_plain is not None
    assert new_plain != old_plain
    assert new_record.key_hash != old_hash
    assert new_record.rotated_from == record.id
    # 旧 key 已吊销
    db_session.refresh(record)
    assert record.is_active == "N"
    # 旧 key 不再可用，新 key 可用
    assert validate_api_key(db_session, old_plain) is None
    found = validate_api_key(db_session, new_plain)
    assert found is not None
    assert found.id == new_record.id


def test_rotate_api_key_not_found(
    db_session: Session, test_tenant: Tenant
) -> None:
    assert (
        rotate_api_key(
            db_session, key_id="ghost", tenant_id=test_tenant.id
        )
        is None
    )


def test_rotate_api_key_other_tenant_returns_none(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    record, _ = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    other = _tenant(db_session, "o3")
    assert (
        rotate_api_key(db_session, key_id=record.id, tenant_id=other.id) is None
    )


# ------------------------------------------------------------------
# revoke_api_key
# ------------------------------------------------------------------


def test_revoke_api_key_success(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    record, plain = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    assert revoke_api_key(
        db_session, key_id=record.id, tenant_id=test_tenant.id
    ) is True
    db_session.refresh(record)
    assert record.is_active == "N"
    assert validate_api_key(db_session, plain) is None


def test_revoke_api_key_not_found(
    db_session: Session, test_tenant: Tenant
) -> None:
    assert (
        revoke_api_key(db_session, key_id="ghost", tenant_id=test_tenant.id)
        is False
    )


def test_revoke_api_key_other_tenant_returns_false(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    record, _ = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    other = _tenant(db_session, "o4")
    assert (
        revoke_api_key(db_session, key_id=record.id, tenant_id=other.id) is False
    )


# ------------------------------------------------------------------
# delete_api_key
# ------------------------------------------------------------------


def test_delete_api_key_success(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    record, _ = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    assert delete_api_key(
        db_session, key_id=record.id, tenant_id=test_tenant.id
    ) is True
    assert (
        db_session.query(ApiKey).filter(ApiKey.id == record.id).first() is None
    )


def test_delete_api_key_not_found(
    db_session: Session, test_tenant: Tenant
) -> None:
    assert delete_api_key(
        db_session, key_id="ghost", tenant_id=test_tenant.id
    ) is False


def test_delete_api_key_other_tenant_returns_false(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    record, _ = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    other = _tenant(db_session, "o5")
    assert (
        delete_api_key(db_session, key_id=record.id, tenant_id=other.id) is False
    )


# ------------------------------------------------------------------
# validate_api_key / get_api_key_owner
# ------------------------------------------------------------------


def test_validate_api_key_success_and_stats(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    record, plain = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    assert record.usage_count in (None, 0)
    assert record.first_used_at is None

    found = validate_api_key(db_session, plain)
    assert found is not None
    assert found.id == record.id
    db_session.refresh(record)
    assert record.usage_count == 1
    assert record.first_used_at is not None
    assert record.last_used_at is not None

    # 再次校验：累计使用次数
    validate_api_key(db_session, plain)
    db_session.refresh(record)
    assert record.usage_count == 2


def test_validate_api_key_inactive(
    db_session: Session, test_tenant: Tenant
) -> None:
    """已禁用的 key 应返回 None."""
    user = _user(db_session, test_tenant)
    record, plain = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    record.is_active = "N"
    db_session.commit()
    assert validate_api_key(db_session, plain) is None


def test_validate_api_key_expired(
    db_session: Session, test_tenant: Tenant
) -> None:
    """已过期的 key 应返回 None."""
    user = _user(db_session, test_tenant)
    record, plain = create_api_key(
        db_session,
        user,
        ApiKeyCreate(name="k1", expires_at=datetime.utcnow() - timedelta(days=1)),
    )
    record.expires_at = datetime.utcnow() - timedelta(hours=1)
    db_session.commit()

    # validate_api_key 内部用 datetime.now(UTC) 比较，SQLite 返回的是 naive。
    # 把 datetime.now 替换为返回 naive（与 expires_at 类型一致），这样比较能正常进行。
    import app.services.api_key_service as svc

    with patch.object(svc, "datetime") as fake_dt:
        fake_dt.now.return_value = datetime.utcnow() + timedelta(hours=1)
        assert validate_api_key(db_session, plain) is None


def test_validate_api_key_wrong_returns_none(
    db_session: Session, test_tenant: Tenant
) -> None:
    """错误 key 应返回 None."""
    assert validate_api_key(db_session, "fa_wrong-key") is None


def test_get_api_key_owner_success(
    db_session: Session, test_tenant: Tenant
) -> None:
    user = _user(db_session, test_tenant)
    _, plain = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    owner = get_api_key_owner(db_session, plain)
    assert owner is not None
    assert owner.id == user.id


def test_get_api_key_owner_inactive_user(
    db_session: Session, test_tenant: Tenant
) -> None:
    """key 仍有效但 user 被禁用时，owner 应为 None."""
    user = _user(db_session, test_tenant)
    _, plain = create_api_key(db_session, user, ApiKeyCreate(name="k1"))
    user.is_active = "N"
    db_session.commit()
    assert get_api_key_owner(db_session, plain) is None


def test_get_api_key_owner_returns_none_for_invalid(
    db_session: Session, test_tenant: Tenant
) -> None:
    assert get_api_key_owner(db_session, "fa_invalid") is None
