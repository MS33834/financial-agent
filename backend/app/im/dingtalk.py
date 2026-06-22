"""钉钉机器人适配器.

参考钉钉官方文档：
- 签名计算：HMAC-SHA256(timestamp + "\n" + app_secret)
- 目前支持 text 类型消息，可扩展 markdown/action_card。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.config import get_settings
from app.im.base import BaseIMBot, IMBotRegistry, IMMessage, send_webhook_with_retry


class DingTalkSignatureError(Exception):
    """钉钉签名验证失败."""

    pass


@IMBotRegistry.register("dingtalk")
class DingTalkBot(BaseIMBot):
    """钉钉群机器人适配器."""

    def __init__(self, app_secret: str | None = None) -> None:
        """初始化.

        Args:
            app_secret: 钉钉机器人加签密钥；未提供则从 Settings 读取。
        """
        settings = get_settings()
        self.app_secret = app_secret or settings.dingtalk_app_secret

    def verify_signature(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        _raw_body: bytes | None = None,
    ) -> bool:
        """验证钉钉 Webhook 签名.

        钉钉在 URL 中传入 timestamp 与 sign，此处从 headers 或 payload 中读取。
        """
        if not self.app_secret:
            return False

        timestamp = headers.get("timestamp") or str(payload.get("timestamp", ""))
        sign = headers.get("sign") or str(payload.get("sign", ""))
        if not timestamp or not sign:
            return False

        expected = self._compute_sign(timestamp)
        return hmac.compare_digest(expected, sign)

    def _compute_sign(self, timestamp: str) -> str:
        """计算钉钉签名."""
        if not self.app_secret:
            return ""
        string_to_sign = f"{timestamp}\n{self.app_secret}"
        mac = hmac.new(
            self.app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(mac).decode("utf-8")

    def parse_message(self, payload: dict[str, Any]) -> IMMessage:
        """解析钉钉 text 消息."""
        text_info = payload.get("text", {})
        sender_staff_id = payload.get("senderStaffId", "")
        # 优先使用 senderStaffId 作为用户标识，否则使用 senderStaffId 为空
        return IMMessage(
            user_id=sender_staff_id,
            username=payload.get("senderNick", ""),
            tenant_id="",  # 需通过 user_id 映射
            text=text_info.get("content", "").strip(),
            raw_payload=payload,
        )

    def build_response(self, content: str, msg_type: str = "text") -> dict[str, Any]:
        """构建钉钉响应消息."""
        if msg_type == "markdown":
            return {
                "msgtype": "markdown",
                "markdown": {"title": "财务智能体", "text": content},
            }
        return {
            "msgtype": "text",
            "text": {"content": content},
        }

    def send_message(self, content: str, msg_type: str = "text") -> bool:
        """通过钉钉机器人 Webhook 主动推送消息."""
        settings = get_settings()
        webhook = settings.dingtalk_webhook
        if not webhook:
            return False

        timestamp = str(int(time.time() * 1000))
        sign = self._compute_sign(timestamp) if self.app_secret else ""
        url = f"{webhook}&timestamp={timestamp}"
        if sign:
            url = f"{url}&sign={sign}"

        body = json.dumps(self.build_response(content, msg_type)).encode("utf-8")
        return send_webhook_with_retry(url, body)
