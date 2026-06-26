"""通知记录模型.

持久化每条通知的发送记录，用于站内信展示与发送审计。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase, now_utc


class Notification(UUIDBase):
    """通知记录."""

    __tablename__ = "notifications"

    recipient: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, comment="接收方（用户 ID / 邮箱 / IM ID）"
    )
    channel: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="渠道: in_app / email / im"
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="通知标题")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="通知正文")
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="normal", comment="优先级"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", comment="发送状态"
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON, nullable=True, default=dict, comment="附加元数据"
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="已读时间"
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=now_utc, comment="发送时间"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "recipient": self.recipient,
            "channel": self.channel,
            "title": self.title,
            "body": self.body,
            "priority": self.priority,
            "status": self.status,
            "metadata": self.metadata_,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
