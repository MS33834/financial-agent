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
    commit: bool = True,
) -> AuditLog:
    """记录一条审计日志.

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
    if commit:
        db.commit()
        db.refresh(log)
    return log
