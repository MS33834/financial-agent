"""SQL 沙箱：仅允许只读 SELECT 查询."""

from __future__ import annotations

import re


class SQLSandboxError(Exception):
    """SQL 沙箱校验失败异常."""

    pass


class SQLSandbox:
    """SQL 安全沙箱，拦截危险语句."""

    # 必须只读
    FORBIDDEN_KEYWORDS: tuple[str, ...] = (
        "insert",
        "update",
        "delete",
        "drop",
        "truncate",
        "alter",
        "create",
        "grant",
        "revoke",
        "exec",
        "execute",
        "usp_",
        "xp_",
        "sp_",
        "into",
        "merge",
        "replace",
        "union",
        "with",
    )

    # 危险函数/子句
    DANGEROUS_PATTERNS: tuple[str, ...] = (
        r";\s*\w+",  # 多语句分号
        r"--",
        r"/\*",
        r"\*/",
        r"xp_cmdshell",
        r"sleep\s*\(",
        r"benchmark\s*\(",
        r"pg_sleep",
        r"dbms_",
    )

    def __init__(self, allowed_tables: list[str] | None = None) -> None:
        """初始化沙箱.

        Args:
            allowed_tables: 允许查询的表白名单，None 表示不限制表名
        """
        self.allowed_tables = set(allowed_tables) if allowed_tables else None

    def validate(self, sql: str) -> None:
        """校验 SQL 是否安全.

        Args:
            sql: 待校验 SQL

        Raises:
            SQLSandboxError: 校验失败
        """
        normalized = sql.strip().lower()

        if not normalized.startswith("select"):
            raise SQLSandboxError("Only SELECT statements are allowed")

        for keyword in self.FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{keyword}\b", normalized):
                raise SQLSandboxError(f"Forbidden keyword detected: {keyword}")

        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                raise SQLSandboxError(f"Dangerous pattern detected: {pattern}")

        if self.allowed_tables:
            used_tables = self._extract_tables(normalized)
            disallowed = used_tables - self.allowed_tables
            if disallowed:
                raise SQLSandboxError(f"Disallowed tables: {', '.join(disallowed)}")

    @staticmethod
    def _extract_tables(sql: str) -> set[str]:
        """简单提取 SQL 中使用的表名（from/join 后）."""
        tables: set[str] = set()
        tokens = sql.replace(",", " ").split()
        for i, token in enumerate(tokens):
            if token in ("from", "join") and i + 1 < len(tokens):
                table = tokens[i + 1].strip("`'\"[]")
                if table:
                    tables.add(table)
        return tables
