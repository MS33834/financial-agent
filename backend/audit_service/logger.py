"""审计日志记录器与模块级便捷函数.

提供可扩展的审计框架入口：

- ``AuditLogger``：管理多个 sink，将事件分发到所有已注册 sink；
- ``log_action``：兼容现有调用方的事务型审计写入函数，同时分发到额外 sink。

设计原则：主审计记录（数据库）由 ``log_action`` 在业务事务中写入以保证原子性；
额外 sink（日志、远程上报等）通过 ``AuditLogger`` 异步分发，失败不影响主流程。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.logger import get_logger
from audit_service.sinks import AuditSink
from audit_service.types import AuditEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.audit_log import AuditLog
    from app.models.user import User

logger = get_logger(__name__)


class AuditLogger:
    """审计事件分发器.

    维护一个 sink 列表，将 ``AuditEvent`` 分发给所有可用 sink。
    单个 sink 抛异常不会中断其他 sink，仅记录 warning。
    """

    def __init__(self, sinks: list[AuditSink] | None = None) -> None:
        self._sinks: list[AuditSink] = list(sinks) if sinks else []

    @property
    def sinks(self) -> list[AuditSink]:
        """当前已注册的 sink 列表（只读视图）."""
        return list(self._sinks)

    def add_sink(self, sink: AuditSink) -> AuditLogger:
        """注册一个 sink，返回 self 便于链式调用."""
        self._sinks.append(sink)
        return self

    def remove_sink(self, name: str) -> bool:
        """按 name 移除一个 sink，返回是否移除成功."""
        before = len(self._sinks)
        self._sinks = [s for s in self._sinks if s.name != name]
        return len(self._sinks) < before

    def clear_sinks(self) -> None:
        """清空所有 sink."""
        self._sinks.clear()

    def log(self, event: AuditEvent) -> None:
        """将事件分发给所有可用 sink. 任何 sink 失败仅记录 warning."""
        for sink in self._sinks:
            if not sink.is_available():
                continue
            try:
                sink.write(event)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "audit_sink_failed",
                    sink=sink.name,
                    error=str(exc),
                    action=event.action,
                )


_default_logger = AuditLogger()


def get_default_logger() -> AuditLogger:
    """获取进程级默认 AuditLogger（用于注册全局额外 sink）."""
    return _default_logger


def log_action(
    db: Session,
    action: str,
    resource: str,
    result: str = "success",
    user: User | None = None,
    input_hash: str | None = None,
    output_hash: str | None = None,
    model_version: str | None = None,
    ip: str | None = None,
    reason: str | None = None,
    commit: bool = True,
) -> AuditLog:
    """记录一条审计日志.

    行为与原 ``app.services.audit_service.log_action`` 完全一致：
    写入 ``audit_logs`` 表，``commit=True`` 时立即提交并刷新。
    额外地，将事件分发到默认 logger 的所有已注册 sink（如日志 sink），
    用于旁路审计。分发失败不影响主流程。

    Args:
        db: 数据库会话。
        action: 动作名称。
        resource: 资源标识。
        result: 结果状态。
        user: 触发用户。
        input_hash: 输入哈希。
        output_hash: 输出哈希。
        model_version: 模型版本。
        ip: 来源 IP。
        reason: 原因说明。
        commit: 是否立即提交事务。当调用方处于更大的事务中时，
            应传入 ``False``，由调用方统一提交以保证原子性。
    """
    from app.models.audit_log import AuditLog

    event = AuditEvent(
        action=action,
        resource=resource,
        result=result,
        tenant_id=user.tenant_id if user else None,
        user_id=user.id if user else None,
        input_hash=input_hash,
        output_hash=output_hash,
        model_version=model_version,
        ip=ip,
        reason=reason,
    )

    log = AuditLog(**event.to_audit_log_kwargs())
    db.add(log)
    if commit:
        db.commit()
        db.refresh(log)

    # 分发到额外 sink（数据库主记录已在上方写入，此处仅处理旁路 sink）
    _default_logger.log(event)

    return log


__all__ = [
    "AuditLogger",
    "get_default_logger",
    "log_action",
]
