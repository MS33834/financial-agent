"""审计事件类型定义."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.user import User


@dataclass(slots=True)
class AuditEvent:
    """审计事件.

    描述一次需要被审计的关键操作。事件会被分发到所有已注册的审计 sink
    （数据库、日志、远程上报等）。``action`` / ``result`` 建议使用
    ``shared.constants.AuditAction`` / ``shared.constants.AuditResult`` 枚举值，
    但为保持模块独立、避免循环依赖，此处使用 ``str`` 类型。
    """

    action: str
    resource: str
    result: str = "success"
    tenant_id: str | None = None
    user_id: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    model_version: str | None = None
    ip: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_user(
        cls,
        user: User | None,
        action: str,
        resource: str,
        **kwargs: Any,
    ) -> AuditEvent:
        """从 User 对象构造事件，自动填充 tenant_id / user_id."""
        return cls(
            action=action,
            resource=resource,
            tenant_id=user.tenant_id if user else None,
            user_id=user.id if user else None,
            **kwargs,
        )

    def to_audit_log_kwargs(self) -> dict[str, Any]:
        """转换为 ``AuditLog`` ORM 构造参数（不含 id / 时间戳）."""
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "model_version": self.model_version,
            "ip": self.ip,
            "result": self.result,
            "reason": self.reason,
        }
