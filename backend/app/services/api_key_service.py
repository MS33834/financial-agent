"""API Key 业务服务.

提供 Key 生成、哈希校验、租户级 CRUD 以及认证查询能力。
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate
from app.schemas.common import PaginationParams

API_KEY_PREFIX = "fa_"
API_KEY_LENGTH = 48


def _hash_key(key: str) -> str:
    """计算 API Key 的 SHA-256 哈希."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    """生成一个带前缀的随机 API Key 明文."""
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(API_KEY_LENGTH)}"


def create_api_key(
    db: Session,
    user: User,
    data: ApiKeyCreate,
) -> tuple[ApiKey, str]:
    """为指定用户创建 API Key.

    Returns:
        (ApiKey 对象, 明文 key)，明文 key 仅返回一次。
    """
    plain_key = generate_api_key()
    key_hash = _hash_key(plain_key)

    api_key = ApiKey(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=data.name,
        key_hash=key_hash,
        scopes=data.scopes or [],
        is_active="Y",
        expires_at=data.expires_at,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key, plain_key


def list_api_keys(
    db: Session,
    tenant_id: str,
    pagination: PaginationParams,
) -> dict[str, Any]:
    """查询租户下的 API Key 列表."""
    query = db.query(ApiKey).filter(ApiKey.tenant_id == tenant_id)
    total = query.count()
    items = (
        query.order_by(ApiKey.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
        .all()
    )
    return {
        "items": [item.to_dict() for item in items],
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
    }


def revoke_api_key(db: Session, key_id: str, tenant_id: str) -> bool:
    """吊销指定 API Key（将 is_active 置为 N）."""
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.tenant_id == tenant_id)
        .first()
    )
    if api_key is None:
        return False
    api_key.is_active = "N"
    db.commit()
    return True


def delete_api_key(db: Session, key_id: str, tenant_id: str) -> bool:
    """删除指定 API Key."""
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.tenant_id == tenant_id)
        .first()
    )
    if api_key is None:
        return False
    db.delete(api_key)
    db.commit()
    return True


def validate_api_key(db: Session, api_key_value: str) -> ApiKey | None:
    """校验 API Key 是否有效，更新最后使用时间，返回 Key 记录."""
    key_hash = _hash_key(api_key_value)
    key_record = (
        db.query(ApiKey)
        .filter(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active == "Y",
        )
        .first()
    )
    if key_record is None:
        return None

    now = datetime.now(UTC)
    if key_record.expires_at is not None and key_record.expires_at < now:
        return None

    key_record.last_used_at = now
    db.commit()
    return key_record


def get_api_key_owner(db: Session, api_key_value: str) -> User | None:
    """校验 API Key 并返回所属用户."""
    key_record = validate_api_key(db, api_key_value)
    if key_record is None:
        return None
    user = db.query(User).filter(User.id == key_record.user_id).first()
    if user is None or user.is_active != "Y":
        return None
    return user
