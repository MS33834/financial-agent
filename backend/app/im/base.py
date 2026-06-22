"""IM 机器人抽象基类与通用模型."""

from __future__ import annotations

import time
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar
from urllib.error import URLError

from pydantic import BaseModel


class IMMessage(BaseModel):
    """统一 IM 消息模型."""

    user_id: str = ""
    username: str = ""
    tenant_id: str = ""
    text: str = ""
    raw_payload: dict[str, Any] | None = None


def send_webhook_with_retry(
    webhook_url: str,
    body: bytes,
    *,
    max_retries: int = 2,
    timeout: int = 10,
) -> bool:
    """向 Webhook 地址发送 POST 请求，失败时自动重试.

    仅对网络层异常（URLError、TimeoutError、OSError）进行重试，
    HTTP 非 200 响应直接返回失败，避免对业务错误无限重试。
    """
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            webhook_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return bool(resp.status == 200)
        except (URLError, TimeoutError, OSError):
            if attempt == max_retries:
                return False
            time.sleep(2 ** attempt)
    return False


class BaseIMBot(ABC):
    """IM 机器人抽象基类.

    子类需实现平台特定的签名验证、消息解析与响应构建，并通过
    `@IMBotRegistry.register(platform_name)` 自动注册到平台注册表。
    """

    platform_name: ClassVar[str] = ""

    @abstractmethod
    def verify_signature(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        raw_body: bytes | None = None,
    ) -> bool:
        """验证 Webhook 请求签名.

        Args:
            payload: 已解析的 JSON 负载。
            headers: 请求头。
            raw_body: 原始请求体字节，部分平台签名需要。
        """
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

    def send_message(self, _content: str, _msg_type: str = "text") -> bool:
        """主动向 IM 平台推送消息.

        默认实现为空操作并返回 False；子类可根据平台 Webhook 实现主动推送。
        未配置 Webhook 或推送失败时均返回 False，不影响主流程。
        """
        return False


class IMBotRegistry:
    """IM 机器人注册表.

    新增 IM 平台只需继承 BaseIMBot 并用 `@IMBotRegistry.register("platform")`
    装饰，路由层即可通过平台名称获取对应机器人，无需修改 if/else 分支。
    """

    _bots: dict[str, type[BaseIMBot]] = {}

    @classmethod
    def register(cls, platform: str) -> Callable[[type[BaseIMBot]], type[BaseIMBot]]:
        """返回类装饰器，将机器人实现注册到指定平台名."""

        def decorator(bot_cls: type[BaseIMBot]) -> type[BaseIMBot]:
            bot_cls.platform_name = platform
            cls._bots[platform] = bot_cls
            return bot_cls

        return decorator

    @classmethod
    def get_bot(cls, platform: str) -> BaseIMBot | None:
        """根据平台名称获取机器人实例."""
        bot_cls = cls._bots.get(platform)
        if bot_cls is None:
            return None
        return bot_cls()

    @classmethod
    def list_platforms(cls) -> list[str]:
        """返回所有已注册平台名称."""
        return list(cls._bots.keys())
