"""租户模型."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.api_key import ApiKey
    from app.models.user import User


class Tenant(UUIDBase):
    """租户/企业实体."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="租户名称")
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="租户编码")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="描述")

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
