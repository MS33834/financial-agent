"""通知服务.

统一调度多渠道通知发送，持久化发送记录，支持渠道降级与错误隔离。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from notification.base import (
    NotificationMessage,
    NotificationResult,
)
from notification.channels import EmailChannel, IMChannel, InAppChannel


class NotificationService:
    """通知服务.

    根据消息指定的 channel 选择对应渠道发送。
    站内信始终可用（写入数据库），邮件/IM 在未配置时自动跳过。
    发送失败不抛异常，返回 FAILED 结果，由调用方决定是否重试。
    """

    def __init__(self, db: Session, settings: Any | None = None) -> None:
        self._db = db
        self._settings = settings
        self._in_app = InAppChannel(db=db)
        self._email: EmailChannel | None = None
        self._im: IMChannel | None = None
        if settings is not None:
            self._email = EmailChannel.from_settings(settings)
            self._im = IMChannel.from_settings(settings)

    def _get_channel(self, channel_name: str) -> Any:
        """根据渠道名返回渠道实例."""
        if channel_name == "in_app":
            return self._in_app
        if channel_name == "email":
            return self._email or EmailChannel()
        if channel_name == "im":
            return self._im or IMChannel()
        raise ValueError(f"未知的通知渠道: {channel_name}")

    def send(self, message: NotificationMessage) -> NotificationResult:
        """发送单条通知.

        站内信渠道需要数据库会话，发送前注入。
        """
        channel = self._get_channel(message.channel)
        if message.channel == "in_app":
            self._in_app.set_db(self._db)
        if not channel.is_available():
            # 站内信作为兜底：外部渠道不可用时降级写站内信
            fallback_msg = NotificationMessage(
                channel="in_app",
                recipient=message.recipient,
                title=f"[{message.channel} 降级] {message.title}",
                body=message.body,
                priority=message.priority,
                metadata={**message.metadata, "original_channel": message.channel},
            )
            return self._in_app.send(fallback_msg)
        return channel.send(message)

    def send_batch(self, messages: list[NotificationMessage]) -> list[NotificationResult]:
        """批量发送通知."""
        return [self.send(msg) for msg in messages]

    def list_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """查询用户站内信列表."""
        from app.models.notification import Notification  # noqa: PLC0415

        query = self._db.query(Notification).filter(
            Notification.recipient == user_id,
            Notification.channel == "in_app",
        )
        if unread_only:
            query = query.filter(Notification.read_at.is_(None))
        items = query.order_by(Notification.created_at.desc()).limit(limit).all()
        return [item.to_dict() for item in items]

    def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """标记站内信为已读."""
        from datetime import UTC, datetime  # noqa: PLC0415

        from app.models.notification import Notification  # noqa: PLC0415

        record = (
            self._db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.recipient == user_id,
            )
            .first()
        )
        if record is None:
            return False
        record.read_at = datetime.now(UTC)
        self._db.commit()
        return True


_service_instance: NotificationService | None = None


def get_notification_service(db: Session, settings: Any | None = None) -> NotificationService:
    """获取通知服务实例（每次请求新建，确保 db 会话正确）."""
    return NotificationService(db, settings)
