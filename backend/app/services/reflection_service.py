"""错误自省服务.

对任务失败、未捕获异常进行自动分类、根因分析与修复建议生成，
形成可查询、可追踪、可闭环的错误自省日志。
"""

from __future__ import annotations

import traceback
from contextlib import suppress

from sqlalchemy.orm import Session

from app.core.errors import classify_exception
from app.models.error_reflection import ErrorReflection
from app.schemas.common import PaginationParams


class ReflectionService:
    """错误自省服务."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def reflect(
        self,
        exc: BaseException,
        *,
        task_name: str | None = None,
        task_id: str | None = None,
        tenant_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> ErrorReflection:
        """对异常进行自省并持久化.

        Args:
            exc: 待分析的异常。
            task_name: 任务名称（可选）。
            task_id: 任务 ID（可选）。
            tenant_id: 租户 ID（可选）。
            resource_type: 资源类型（可选）。
            resource_id: 资源 ID（可选）。

        Returns:
            创建的错误自省日志记录。
        """
        category = classify_exception(exc)
        with suppress(Exception):
            from app.metrics import FA_ERRORS_CLASSIFIED_TOTAL

            FA_ERRORS_CLASSIFIED_TOTAL.labels(error_category=category).inc()
        exc_type = type(exc).__name__
        exc_message = str(exc) or "无异常消息"
        stack_trace = traceback.format_exc() if category in {"unknown", "retryable"} else None

        root_cause, suggested_fix = self._analyze(exc, exc_type, category)

        reflection = ErrorReflection(
            tenant_id=tenant_id,
            task_name=task_name,
            task_id=task_id,
            resource_type=resource_type,
            resource_id=resource_id,
            exception_type=exc_type,
            exception_message=exc_message,
            stack_trace=stack_trace,
            error_category=category,
            root_cause=root_cause,
            suggested_fix=suggested_fix,
        )
        self.db.add(reflection)
        self.db.commit()
        self.db.refresh(reflection)
        return reflection

    def _analyze(
        self, _exc: BaseException, exc_type: str, category: str
    ) -> tuple[str | None, str | None]:
        """基于规则生成根因与修复建议."""
        analyzers: dict[str, tuple[str, str]] = {
            "retryable": (
                "临时基础设施故障，如数据库连接中断、网络超时或外部服务不可用。",
                "检查网络/数据库/外部服务状态后重试；若频繁出现，请扩容或增加连接池。",
            ),
            "business": (
                "业务规则未满足，如参数校验失败、资源状态不正确或权限不足。",
                "核对输入参数与业务状态，修正后重新触发任务，无需简单重试。",
            ),
            "config": (
                "配置缺失或错误，导致服务无法正常执行。",
                "检查环境变量、配置文件与密钥设置，修复后重启服务。",
            ),
            "security": (
                "安全策略拦截，如越权访问、签名失败或疑似注入行为。",
                "确认调用方身份与权限，检查请求合法性，必要时审计并告警。",
            ),
        }

        if category in analyzers:
            return analyzers[category]

        return (
            f"未分类异常 {exc_type}，需结合堆栈进一步排查。",
            "查看完整堆栈与相关日志，定位异常触发路径后修复。",
        )

    def list_reflections(
        self,
        tenant_id: str | None,
        *,
        category: str | None = None,
        resolved: bool | None = None,
        resource_type: str | None = None,
        pagination: PaginationParams | None = None,
    ) -> tuple[list[ErrorReflection], int]:
        """查询错误自省日志列表."""
        query = self.db.query(ErrorReflection)
        if tenant_id is not None:
            query = query.filter(ErrorReflection.tenant_id == tenant_id)
        if category:
            query = query.filter(ErrorReflection.error_category == category)
        if resolved is not None:
            query = query.filter(ErrorReflection.resolved.is_(resolved))
        if resource_type:
            query = query.filter(ErrorReflection.resource_type == resource_type)

        total = query.count()
        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
            query = (
                query.order_by(ErrorReflection.created_at.desc())
                .offset(offset)
                .limit(pagination.page_size)
            )
        else:
            query = query.order_by(ErrorReflection.created_at.desc())

        return query.all(), total

    def get_reflection(self, reflection_id: str, tenant_id: str | None = None) -> ErrorReflection | None:
        """获取单条自省日志."""
        query = self.db.query(ErrorReflection).filter(ErrorReflection.id == reflection_id)
        if tenant_id is not None:
            query = query.filter(ErrorReflection.tenant_id == tenant_id)
        return query.first()

    def resolve(
        self,
        reflection_id: str,
        resolution: str,
        tenant_id: str | None = None,
    ) -> ErrorReflection | None:
        """标记自省日志为已解决并记录解决方案."""
        reflection = self.get_reflection(reflection_id, tenant_id=tenant_id)
        if reflection is None:
            return None
        reflection.resolved = True
        reflection.resolution = resolution
        self.db.commit()
        self.db.refresh(reflection)
        return reflection


def create_reflection(
    db: Session,
    exc: BaseException,
    *,
    task_name: str | None = None,
    task_id: str | None = None,
    tenant_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> ErrorReflection:
    """便捷函数：直接创建错误自省日志."""
    return ReflectionService(db).reflect(
        exc,
        task_name=task_name,
        task_id=task_id,
        tenant_id=tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
