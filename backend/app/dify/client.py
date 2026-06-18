"""Dify Workflow API 客户端.

封装对 Dify Workflow Run API 的调用，支持阻塞式执行并返回结构化结果。
"""

from typing import Any, cast

import httpx

from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)


class DifyClientError(Exception):
    """Dify 客户端异常."""

    pass


class DifyClient:
    """调用 Dify Workflow/API 的轻量客户端.

    默认从 Settings 读取 ``dify_base_url`` 与 ``dify_api_key``。
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """初始化客户端.

        Args:
            base_url: Dify API 基础地址，如 ``http://localhost:5001/v1``。
            api_key: Dify Workflow/API 密钥。

        Raises:
            DifyClientError: 未配置 base_url 或 api_key。
        """
        settings = get_settings()
        self.base_url = (base_url or settings.dify_base_url or "").rstrip("/")
        self.api_key = api_key or settings.dify_api_key

        if not self.base_url:
            raise DifyClientError("DIFY_BASE_URL is not configured")
        if not self.api_key:
            raise DifyClientError("DIFY_API_KEY is not configured")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def run_workflow(
        self,
        inputs: dict[str, Any],
        response_mode: str = "blocking",
        user: str = "financial-agent",
    ) -> dict[str, Any]:
        """运行 Dify Workflow.

        Args:
            inputs: Workflow 输入变量。
            response_mode: ``blocking`` 或 ``streaming``，MVP 默认阻塞。
            user: Dify 用户标识，用于区分会话/租户。

        Returns:
            Dify 返回的原始 JSON 数据。

        Raises:
            DifyClientError: 调用失败或返回非 200 状态码。
        """
        url = f"{self.base_url}/workflows/run"
        payload = {
            "inputs": inputs,
            "response_mode": response_mode,
            "user": user,
        }

        try:
            response = httpx.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "dify_workflow_http_error",
                status=exc.response.status_code,
                body=exc.response.text,
                url=url,
            )
            raise DifyClientError(
                f"Dify workflow returned {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            logger.error("dify_workflow_request_error", error=str(exc), url=url)
            raise DifyClientError(f"Failed to call Dify workflow: {exc!s}") from exc

        return cast(dict[str, Any], response.json())

    def parse_answer(self, workflow_result: dict[str, Any]) -> str:
        """从 Workflow 结果中提取文本答案.

        兼容 Dify Chatflow/Workflow 的常用返回结构。
        """
        if "answer" in workflow_result:
            return str(workflow_result["answer"])
        if "data" in workflow_result and "outputs" in workflow_result["data"]:
            outputs = workflow_result["data"]["outputs"]
            if isinstance(outputs, dict):
                for key in ("answer", "text", "result"):
                    if key in outputs:
                        return str(outputs[key])
                return str(outputs)
        return str(workflow_result)
