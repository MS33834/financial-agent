"""Ollama LLM 客户端封装."""

from __future__ import annotations

import json

import httpx

from app.config import get_settings


class LLMUnavailableError(Exception):
    """LLM 服务不可用异常."""

    pass


class LLMClient:
    """基于 Ollama HTTP API 的轻量 LLM 客户端."""

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """初始化客户端.

        Args:
            model: Ollama 模型名，默认从配置读取。
            host: Ollama 服务地址，默认从配置读取。
            timeout: 请求超时（秒）。
        """
        settings = get_settings()
        self.model = model or settings.agent_llm_model
        self.host = host or settings.ollama_host
        self.timeout = timeout

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """调用 Ollama /api/chat 接口并返回生成文本.

        Args:
            system_prompt: 系统提示词。
            user_prompt: 用户提示词。

        Returns:
            模型生成的文本内容。

        Raises:
            LLMUnavailableError: 当 Ollama 不可达或返回非 200 时抛出。
        """
        url = f"{self.host.rstrip('/')}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        try:
            response = httpx.post(
                url,
                json=payload,
                timeout=self.timeout,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailableError(f"无法连接到 Ollama: {exc!s}") from exc

        if response.status_code != 200:
            raise LLMUnavailableError(
                f"Ollama 返回错误状态码 {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise LLMUnavailableError(f"Ollama 返回非 JSON: {exc!s}") from exc

        message = data.get("message", {})
        content = message.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        return content.strip()
