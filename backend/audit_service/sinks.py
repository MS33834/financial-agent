"""审计 sink 实现.

Sink 是审计事件的出口。每个 sink 负责将事件写入一种存储/通道。
``DatabaseAuditSink`` 写入主数据库（参与业务事务）；
``LoggingAuditSink`` 输出结构化日志（不参与事务，用于快速排查）。

自定义 sink 只需实现 ``AuditSink`` Protocol 即可通过 ``AuditLogger.add_sink`` 注册。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from app.logger import get_logger
from audit_service.types import AuditEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger(__name__)


@runtime_checkable
class AuditSink(Protocol):
    """审计事件出口协议."""

    name: str

    def write(self, event: AuditEvent) -> None:
        """写入一条审计事件. 不应抛出异常；失败应被 logger 捕获."""
        ...

    def is_available(self) -> bool:
        """当前是否可用. 不可用的 sink 会被跳过."""
        ...


class DatabaseAuditSink:
    """数据库审计 sink.

    写入 ``audit_logs`` 表，参与调用方的事务（不自行 commit）。
    实际 commit/refresh 由 ``log_action`` 在主流程中统一处理，本 sink 仅负责 add。
    """

    name = "database"

    def __init__(self, db: Session | None = None) -> None:
        self._db = db

    def bind(self, db: Session) -> DatabaseAuditSink:
        """绑定数据库会话，返回新实例（便于在事务中复用）."""
        return DatabaseAuditSink(db)

    def write(self, event: AuditEvent) -> None:
        if self._db is None:
            return
        from app.models.audit_log import AuditLog

        self._db.add(AuditLog(**event.to_audit_log_kwargs()))

    def is_available(self) -> bool:
        return self._db is not None


class LoggingAuditSink:
    """结构化日志审计 sink.

    将审计事件以结构化日志输出，便于通过日志系统（ELK/Loki）检索审计轨迹。
    始终可用，不依赖数据库，适合作为兜底/旁路审计。
    """

    name = "logging"

    def __init__(self) -> None:
        self._logger = get_logger("audit")

    def write(self, event: AuditEvent) -> None:
        self._logger.info(
            "audit_event",
            action=event.action,
            resource=event.resource,
            result=event.result,
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            reason=event.reason,
        )

    def is_available(self) -> bool:
        return True


class CallbackAuditSink:
    """回调审计 sink.

    用于测试或临时将审计事件转发到任意可调用对象（如消息队列、外部 API）。
    """

    name = "callback"

    def __init__(self, callback: Any, *, sink_name: str = "callback") -> None:
        self._callback = callback
        self.name = sink_name
        self._available = True

    def write(self, event: AuditEvent) -> None:
        self._callback(event)

    def is_available(self) -> bool:
        return self._available

    def disable(self) -> None:
        self._available = False
