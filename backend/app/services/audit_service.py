"""审计日志服务.

所有关键操作均应调用本服务记录审计日志。
审计日志只写不删不改，保留期由 DBA/运维策略控制。
"""

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


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
) -> AuditLog:
    """记录一条审计日志."""
    log = AuditLog(
        tenant_id=user.tenant_id if user else None,
        user_id=user.id if user else None,
        action=action,
        resource=resource,
        result=result,
        input_hash=input_hash,
        output_hash=output_hash,
        model_version=model_version,
        ip=ip,
        reason=reason,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
