"""Mineru / Magic-PDF HTTP 解析客户端."""

from typing import Any

import httpx

from app.parser.utils import extract_period, extract_year


class MineruError(Exception):
    """Mineru 请求或结果解析异常."""


class MineruNotConfigured(MineruError):  # noqa: N818
    """Mineru API 地址未配置."""


class MineruClient:
    """调用外部 Mineru HTTP 服务解析 PDF."""

    def __init__(self, api_url: str | None = None, timeout: int = 120) -> None:
        """初始化客户端.

        Args:
            api_url: Mineru 解析服务 HTTP API 地址。
            timeout: 请求超时（秒）。
        """
        self.api_url = api_url
        self.timeout = timeout

    def parse(self, content: bytes, filename: str) -> dict[str, Any]:
        """解析 PDF 内容.

        Args:
            content: PDF 文件字节。
            filename: 原始文件名。

        Returns:
            解析结果字典，包含 records、text、confidence 等字段。

        Raises:
            MineruNotConfigured: 未配置 api_url。
            MineruError: 请求失败或返回结果无法解析。
        """
        if not self.api_url:
            raise MineruNotConfigured("Mineru API URL 未配置")

        try:
            response = httpx.post(
                f"{self.api_url.rstrip('/')}/parse",
                files={"file": (filename, content, "application/pdf")},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise MineruError(f"Mineru 请求失败: {exc}") from exc
        except ValueError as exc:
            raise MineruError(f"Mineru 返回非 JSON 响应: {exc}") from exc

        tables = payload.get("tables") or []
        records = _flatten_tables(tables)
        text = payload.get("text", "")
        confidence = payload.get("confidence", 0.85)

        return {
            "format": "mineru",
            "filename": filename,
            "extension": "pdf",
            "detected_year": extract_year(filename),
            "detected_period": extract_period(filename),
            "pages": payload.get("pages"),
            "tables": tables,
            "records": records,
            "text": text,
            "confidence": confidence,
        }


def _flatten_tables(tables: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """将 Mineru 返回的多页表格扁平化为 records 列表."""
    records: list[dict[str, Any]] = []
    for table in tables:
        for row in table:
            if isinstance(row, dict):
                records.append(row)
    return records
