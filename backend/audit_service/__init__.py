"""审计服务独立模块.

将关键操作审计能力沉淀为可扩展的审计框架：

- ``AuditEvent``：审计事件数据结构；
- ``AuditSink`` Protocol + ``DatabaseAuditSink`` / ``LoggingAuditSink`` / ``CallbackAuditSink``：
  可插拔的审计出口；
- ``AuditLogger``：多 sink 分发器；
- ``log_action``：事务型审计写入函数（向后兼容 ``app.services.audit_service.log_action``）。

典型用法::

    from audit_service import log_action, get_default_logger, LoggingAuditSink

    # 注册旁路审计 sink（如结构化日志）
    get_default_logger().add_sink(LoggingAuditSink())

    # 在业务事务中记录审计（主记录写入 DB，同时分发到旁路 sink）
    log_action(db, action="create", resource="report:123", user=current_user, commit=False)

现有调用方 ``from app.services.audit_service import log_action`` 无需改动，
``app.services.audit_service`` 已委托到本模块。
"""

from audit_service.logger import AuditLogger, get_default_logger, log_action
from audit_service.sinks import (
    CallbackAuditSink,
    DatabaseAuditSink,
    LoggingAuditSink,
)
from audit_service.types import AuditEvent

__all__ = [
    "AuditEvent",
    "AuditLogger",
    "AuditSink",
    "DatabaseAuditSink",
    "LoggingAuditSink",
    "CallbackAuditSink",
    "get_default_logger",
    "log_action",
]
