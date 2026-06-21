"""异步任务工具函数."""

from sqlalchemy.exc import OperationalError


def is_retryable_error(exc: BaseException) -> bool:
    """仅对网络、连接、超时等临时故障允许重试。"""
    return isinstance(exc, (OperationalError, ConnectionError, TimeoutError, OSError))
