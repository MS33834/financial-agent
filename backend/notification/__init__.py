"""通知服务模块.

提供邮件 / IM / 站内信多渠道通知能力，支持模板渲染、异步发送与发送记录持久化。

用法::

    from notification import NotificationService, NotificationMessage

    service = NotificationService(db)
    service.send(NotificationMessage(
        channel="in_app",
        recipient="user-uuid",
        title="报告已生成",
        body="Q2 利润表已生成，请前往查看。",
    ))
"""

from notification.base import (
    NotificationChannel,
    NotificationMessage,
    NotificationPriority,
    NotificationResult,
    NotificationStatus,
)
from notification.channels import (
    EmailChannel,
    IMChannel,
    InAppChannel,
)
from notification.service import NotificationService, get_notification_service

__all__ = [
    "NotificationChannel",
    "NotificationMessage",
    "NotificationPriority",
    "NotificationResult",
    "NotificationStatus",
    "NotificationService",
    "EmailChannel",
    "InAppChannel",
    "IMChannel",
    "get_notification_service",
]
