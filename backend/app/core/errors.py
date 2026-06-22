"""统一异常分类与错误自省工具.

为所有业务异常建立可重试、业务、配置、安全、未知五大类别，
便于 Celery 任务决策与后续根因分析。
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """业务异常基类."""

    category: str = "business"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class RetryableError(AppError):
    """临时故障，可重试."""

    category: str = "retryable"


class BusinessError(AppError):
    """业务规则错误，不应重试."""

    category: str = "business"


class ConfigError(AppError):
    """配置缺失或错误，需人工修复."""

    category: str = "config"


class SecurityError(AppError):
    """安全相关异常，如越权、注入尝试."""

    category: str = "security"


class UnknownError(AppError):
    """未分类异常."""

    category: str = "unknown"


# 映射常见第三方/标准异常到分类，便于统一处理
_CATEGORY_OVERRIDES: dict[str, str] = {
    "OperationalError": "retryable",
    "ConnectionError": "retryable",
    "TimeoutError": "retryable",
    "OSError": "retryable",
    "SSLError": "retryable",
    "HTTPError": "retryable",
    "ValidationError": "business",
    "ValueError": "business",
    "TypeError": "business",
    "KeyError": "business",
    "AttributeError": "business",
    "FileNotFoundError": "config",
    "PermissionError": "security",
}


def classify_exception(exc: BaseException) -> str:
    """根据异常类型返回分类标签.

    优先读取异常自身的 ``category`` 属性，再按常见类型兜底。
    """
    category = getattr(exc, "category", None)
    if isinstance(category, str):
        return category

    exc_type = type(exc).__name__
    return _CATEGORY_OVERRIDES.get(exc_type, "unknown")


def is_retryable(exc: BaseException) -> bool:
    """判断异常是否属于临时故障，可进行重试."""
    return classify_exception(exc) == "retryable"
