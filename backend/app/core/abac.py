"""ABAC（基于属性的访问控制）策略引擎.

与现有 RBAC 共存：RBAC 做粗粒度角色校验，ABAC 做细粒度属性策略校验。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.access_policy import AccessPolicy
from app.models.user import User


class ABACEngine:
    """ABAC 策略评估引擎."""

    # 支持的条件操作符
    OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains"}

    def __init__(self, db: Session) -> None:
        """初始化引擎.

        Args:
            db: 数据库会话。
        """
        self.db = db

    def evaluate(
        self,
        user: User,
        resource_type: str,
        action: str,
        resource_attributes: dict[str, Any] | None = None,
    ) -> bool:
        """评估用户是否允许对资源执行操作.

        规则：
        1. 按 priority 升序、id 升序排序策略。
        2. 匹配资源类型、操作、租户的策略。
        3. 条件全部满足时应用策略 effect。
        4. 默认拒绝（无任何 allow 策略匹配时）。
        5. deny 策略优先级高于 allow。

        Args:
            user: 当前用户。
            resource_type: 资源类型。
            action: 操作。
            resource_attributes: 资源属性（可选）。

        Returns:
            True 表示允许，False 表示拒绝。
        """
        policies = (
            self.db.query(AccessPolicy)
            .filter(
                AccessPolicy.tenant_id == user.tenant_id,
                AccessPolicy.resource_type == resource_type,
                AccessPolicy.action == action,
                AccessPolicy.is_active.is_(True),
            )
            .order_by(AccessPolicy.priority.asc(), AccessPolicy.id.asc())
            .all()
        )

        allowed = False
        for policy in policies:
            if self._match_conditions(user, resource_attributes or {}, policy.conditions):
                if policy.effect == "deny":
                    return False
                if policy.effect == "allow":
                    allowed = True

        return allowed

    def _match_conditions(
        self,
        user: User,
        resource_attributes: dict[str, Any],
        conditions: dict[str, Any] | None,
    ) -> bool:
        """判断策略条件是否全部满足."""
        if not conditions:
            return True

        context = self._build_context(user, resource_attributes)
        for key, expected in conditions.items():
            actual = self._get_nested_value(context, key)
            if not self._compare(actual, expected):
                return False
        return True

    def _build_context(
        self,
        user: User,
        resource_attributes: dict[str, Any],
    ) -> dict[str, Any]:
        """构建评估上下文."""
        return {
            "user": {
                "id": user.id,
                "role": user.role,
                **(user.attributes or {}),
            },
            "resource": resource_attributes,
        }

    @staticmethod
    def _get_nested_value(context: dict[str, Any], key: str) -> Any:
        """按点号路径获取嵌套值."""
        parts = key.split(".")
        value: Any = context
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    def _compare(self, actual: Any, expected: Any) -> bool:
        """比较实际值与条件期望值.

        支持的操作符格式：
        - ``eq:value`` / ``value``（默认 eq）
        - ``ne:value``
        - ``gt:value`` / ``gte:value`` / ``lt:value`` / ``lte:value``
        - ``in:a,b,c``
        - ``nin:a,b,c``
        - ``contains:value``（用于列表/字符串）
        """
        if isinstance(expected, str) and ":" in expected:
            op, _, raw_value = expected.partition(":")
            if op in self.OPERATORS:
                return self._apply_operator(actual, op, raw_value)

        return bool(actual == expected)

    def _apply_operator(self, actual: Any, op: str, raw_value: str) -> bool:
        """应用操作符."""
        if op == "eq":
            return bool(actual == self._coerce(actual, raw_value))
        if op == "ne":
            return bool(actual != self._coerce(actual, raw_value))

        coerced = self._coerce_numeric(raw_value)
        actual_numeric = self._coerce_numeric(actual)

        if op == "gt":
            return bool(actual_numeric is not None and coerced is not None and actual_numeric > coerced)
        if op == "gte":
            return bool(actual_numeric is not None and coerced is not None and actual_numeric >= coerced)
        if op == "lt":
            return bool(actual_numeric is not None and coerced is not None and actual_numeric < coerced)
        if op == "lte":
            return bool(actual_numeric is not None and coerced is not None and actual_numeric <= coerced)

        values = [self._coerce(actual, v) for v in raw_value.split(",")]
        if op == "in":
            return bool(actual in values)
        if op == "nin":
            return bool(actual not in values)
        if op == "contains":
            return isinstance(actual, list) and any(v in actual for v in values)

        return False

    @staticmethod
    def _coerce(actual: Any, raw_value: str) -> Any:
        """根据 actual 类型转换 raw_value."""
        if isinstance(actual, bool):
            return raw_value.lower() in ("true", "1", "yes")
        if isinstance(actual, int):
            try:
                return int(raw_value)
            except ValueError:
                return raw_value
        if isinstance(actual, float):
            try:
                return float(raw_value)
            except ValueError:
                return raw_value
        return raw_value

    @staticmethod
    def _coerce_numeric(value: Any) -> float | int | None:
        """将值转换为数字，失败返回 None."""
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                if "." in value:
                    return float(value)
                return int(value)
            except ValueError:
                return None
        return None
