"""通知渠道实现.

包含邮件、IM（钉钉/飞书/企微 Webhook）、站内信三个渠道。
每个渠道在配置缺失时自动降级为 SKIPPED，不阻塞主流程。
"""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from typing import Any

from notification.base import (
    NotificationMessage,
    NotificationResult,
    NotificationStatus,
)


class InAppChannel:
    """站内信渠道.

    将通知写入数据库 notification 表，用户在前端消息中心查看。
    这是默认始终可用的兜底渠道，不依赖任何外部服务。
    """

    name = "in_app"

    def __init__(self, db: Any = None) -> None:
        # db 由 NotificationService 在发送时注入
        self._db = db

    def set_db(self, db: Any) -> None:
        self._db = db

    def is_available(self) -> bool:
        return True

    def send(self, message: NotificationMessage) -> NotificationResult:
        if self._db is None:
            return NotificationResult(
                status=NotificationStatus.FAILED,
                message="站内信渠道未注入数据库会话",
            )
        from app.models.notification import Notification  # noqa: PLC0415

        record = Notification(
            recipient=message.recipient,
            channel="in_app",
            title=message.title,
            body=message.body,
            priority=message.priority.value,
            status=NotificationStatus.SENT.value,
            metadata=message.metadata,
        )
        self._db.add(record)
        self._db.commit()
        return NotificationResult(
            status=NotificationStatus.SENT,
            external_id=record.id,
        )


class EmailChannel:
    """邮件渠道（SMTP）.

    配置项：
        SMTP_HOST / SMTP_PORT / SMTP_USERNAME / SMTP_PASSWORD / SMTP_FROM
    配置缺失时 is_available 返回 False，发送时返回 SKIPPED。
    """

    name = "email"

    def __init__(
        self,
        host: str = "",
        port: int = 587,
        username: str = "",
        password: str = "",
        from_addr: str = "",
        use_tls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.use_tls = use_tls

    @classmethod
    def from_settings(cls, settings: Any) -> EmailChannel:
        """从 Settings 构建邮件渠道."""
        return cls(
            host=getattr(settings, "smtp_host", "") or "",
            port=int(getattr(settings, "smtp_port", 587) or 587),
            username=getattr(settings, "smtp_username", "") or "",
            password=getattr(settings, "smtp_password", "") or "",
            from_addr=getattr(settings, "smtp_from", "") or "",
            use_tls=bool(getattr(settings, "smtp_use_tls", True)),
        )

    def is_available(self) -> bool:
        return bool(self.host and self.from_addr)

    def send(self, message: NotificationMessage) -> NotificationResult:
        if not self.is_available():
            return NotificationResult(
                status=NotificationStatus.SKIPPED,
                message="邮件渠道未配置 SMTP_HOST/SMTP_FROM",
            )
        try:
            mime = MIMEText(message.body, "plain", "utf-8")
            mime["Subject"] = message.title
            mime["From"] = self.from_addr
            mime["To"] = message.recipient
            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, [message.recipient], mime.as_string())
            return NotificationResult(status=NotificationStatus.SENT)
        except Exception as exc:  # noqa: BLE001
            return NotificationResult(
                status=NotificationStatus.FAILED,
                message=f"邮件发送失败: {exc}",
            )


class IMChannel:
    """IM Webhook 渠道（钉钉/飞书/企微）.

    通过项目已有的 IM Bot 配置推送消息。配置缺失时返回 SKIPPED。
    """

    name = "im"

    def __init__(
        self,
        dingtalk_webhook: str = "",
        feishu_webhook: str = "",
        wecom_webhook: str = "",
    ) -> None:
        self.dingtalk_webhook = dingtalk_webhook
        self.feishu_webhook = feishu_webhook
        self.wecom_webhook = wecom_webhook

    @classmethod
    def from_settings(cls, settings: Any) -> IMChannel:
        """从 Settings 构建 IM 渠道."""
        return cls(
            dingtalk_webhook=getattr(settings, "dingtalk_webhook", "") or "",
            feishu_webhook=getattr(settings, "feishu_webhook", "") or "",
            wecom_webhook=getattr(settings, "wecom_webhook", "") or "",
        )

    def is_available(self) -> bool:
        return bool(self.dingtalk_webhook or self.feishu_webhook or self.wecom_webhook)

    def send(self, message: NotificationMessage) -> NotificationResult:
        import json  # noqa: PLC0415
        import urllib.request  # noqa: PLC0415

        webhook = (
            self.dingtalk_webhook
            or self.feishu_webhook
            or self.wecom_webhook
        )
        if not webhook:
            return NotificationResult(
                status=NotificationStatus.SKIPPED,
                message="IM 渠道未配置任何 Webhook",
            )
        # 根据 webhook 域名判断平台，构造对应格式
        payload: dict[str, Any]
        if "oapi.dingtalk.com" in webhook:
            payload = {
                "msgtype": "text",
                "text": {"content": f"{message.title}\n{message.body}"},
            }
        elif "open.feishu.cn" in webhook:
            payload = {
                "msg_type": "text",
                "content": {"text": f"{message.title}\n{message.body}"},
            }
        else:
            # 企微格式
            payload = {
                "msgtype": "text",
                "text": {"content": f"{message.title}\n{message.body}"},
            }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                webhook, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            return NotificationResult(status=NotificationStatus.SENT)
        except Exception as exc:  # noqa: BLE001
            return NotificationResult(
                status=NotificationStatus.FAILED,
                message=f"IM 推送失败: {exc}",
            )
