"""通知服务基础定义."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class NotificationStatus(StrEnum):
    """通知发送状态."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class NotificationPriority(StrEnum):
    """通知优先级."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NotificationMessage:
    """通知消息载体.

    Attributes:
        channel: 发送渠道（email / im / in_app）。
        recipient: 接收方标识（邮箱地址 / IM 用户 ID / 系统用户 ID）。
        title: 通知标题。
        body: 通知正文（纯文本）。
        priority: 优先级，默认 normal。
        metadata: 附加元数据（如 report_id、template_name、变量参数）。
    """

    channel: str
    recipient: str
    title: str
    body: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationResult:
    """单次发送结果."""

    status: NotificationStatus
    message: str = ""
    external_id: str | None = None


class NotificationChannel(Protocol):
    """通知渠道协议.

    每个具体渠道（邮件 / IM / 站内信）实现此协议。
    """

    name: str

    def send(self, message: NotificationMessage) -> NotificationResult:
        """发送通知，返回发送结果."""
        ...

    def is_available(self) -> bool:
        """渠道是否可用（配置完整且依赖就绪）."""
        ...
