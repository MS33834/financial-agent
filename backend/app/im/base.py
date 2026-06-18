"""IM 机器人抽象基类与通用模型."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class IMMessage(BaseModel):
    """统一 IM 消息模型."""

    user_id: str = ""
    username: str = ""
    tenant_id: str = ""
    text: str = ""
    raw_payload: dict[str, Any] | None = None


class BaseIMBot(ABC):
    """IM 机器人抽象基类.

    子类需实现平台特定的签名验证、消息解析与响应构建。
    """

    @abstractmethod
    def verify_signature(self, payload: dict[str, Any], headers: dict[str, str]) -> bool:
        """验证 Webhook 请求签名."""
        raise NotImplementedError

    @abstractmethod
    def parse_message(self, payload: dict[str, Any]) -> IMMessage:
        """解析平台消息为统一消息模型."""
        raise NotImplementedError

    @abstractmethod
    def build_response(self, content: str, msg_type: str = "text") -> dict[str, Any]:
        """构建平台响应消息."""
        raise NotImplementedError

    def build_error_response(self, error: str) -> dict[str, Any]:
        """构建错误响应."""
        return self.build_response(f"请求处理失败：{error}", msg_type="text")
