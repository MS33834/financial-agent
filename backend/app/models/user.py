"""用户模型."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class User(UUIDBase):
    """系统用户."""

    __tablename__ = "users"

    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属租户",
    )
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="用户名"
    )
    email: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="邮箱")
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希"
    )
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="viewer", comment="角色"
    )
    is_active: Mapped[str] = mapped_column(
        String(1), nullable=False, default="Y", comment="是否启用"
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="users")

    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_tenant_username"),
    )
