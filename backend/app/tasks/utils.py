"""异步任务工具函数."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import classify_exception
from app.core.errors import is_retryable as _is_retryable
from app.logger import get_logger
from app.services.reflection_service import create_reflection

logger = get_logger(__name__)


def is_retryable_error(exc: BaseException) -> bool:
    """仅对网络、连接、超时等临时故障允许重试."""
    return _is_retryable(exc)


def reflect_task_failure(
    db: Session,
    exc: BaseException,
    *,
    task_name: str | None = None,
    task_id: str | None = None,
    tenant_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> None:
    """记录任务失败自省日志.

    失败不应阻塞主流程，因此捕获所有异常避免级联错误。
    但会记录日志以便排查自省服务本身的故障。
    """
    try:
        create_reflection(
            db,
            exc,
            task_name=task_name,
            task_id=task_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    except Exception as reflect_exc:  # noqa: BLE001
        logger.warning(
            "reflection_failed",
            task_name=task_name,
            task_id=task_id,
            error=str(reflect_exc),
        )


def classify_task_error(exc: BaseException) -> str:
    """返回任务异常分类."""
    return classify_exception(exc)
