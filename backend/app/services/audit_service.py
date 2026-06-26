"""审计日志服务（向后兼容模块）.

实际审计框架已迁移到顶层 ``audit_service`` 包，提供可插拔的 sink 机制。
本模块保留以兼容现有 ``from app.services.audit_service import log_action`` 调用，
``log_action`` 委托给 ``audit_service.log_action``，行为与原实现完全一致。
"""

from audit_service import (
    AuditEvent,
    AuditLogger,
    DatabaseAuditSink,
    LoggingAuditSink,
    get_default_logger,
    log_action,
)

__all__ = [
    "log_action",
    "AuditEvent",
    "AuditLogger",
    "DatabaseAuditSink",
    "LoggingAuditSink",
    "get_default_logger",
]
