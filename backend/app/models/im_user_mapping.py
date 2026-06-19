"""IM 用户映射模型.

将各 IM 平台（钉钉、飞书、企业微信）的用户 ID 与系统用户解耦维护，
替代原先直接存储在 user.attributes 中的方式，便于独立管理、审计和扩展。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.user import User


class IMUserMapping(UUIDBase):
    """IM 用户与系统用户映射."""

    __tablename__ = "im_user_mappings"

    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属租户",
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="系统用户 ID",
    )
    platform: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="IM 平台，如 dingtalk / feishu / wecom",
    )
    im_user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        comment="IM 平台用户唯一标识",
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        server_onupdate=sa.func.now(),
        nullable=False,
        comment="更新时间",
    )

    user: Mapped["User"] = relationship(back_populates="im_mappings")

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "platform", "im_user_id", name="uq_tenant_platform_im_user"
        ),
    )
