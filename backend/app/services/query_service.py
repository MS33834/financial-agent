"""自然语言查询服务."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.text2sql.base import Text2SQLBackend
from app.text2sql.rule_backend import RuleBasedText2SQLBackend
from app.text2sql.sql_sandbox import SQLSandbox, SQLSandboxError


class QueryService:
    """自然语言查询服务.

    负责选择 Text2SQL 后端、沙箱校验、执行 SQL 并返回结果。
    """

    def __init__(self, backend: Text2SQLBackend | None = None) -> None:
        """初始化查询服务.

        Args:
            backend: Text2SQL 后端，默认根据配置选择
        """
        self.backend = backend or self._default_backend()
        self.sandbox = SQLSandbox(
            allowed_tables=["financial_reports", "accounts", "vouchers"],
        )

    @staticmethod
    def _default_backend() -> Text2SQLBackend:
        """根据配置返回默认 Text2SQL 后端."""
        settings = get_settings()
        if settings.text2sql_backend == "vanna":
            from app.text2sql.vanna_backend import VannaText2SQLBackend

            return VannaText2SQLBackend(
                model=settings.ollama_model,
                host=settings.ollama_host,
            )
        return RuleBasedText2SQLBackend()

    def nl2sql(
        self,
        question: str,
        tenant_id: str,
        db: Session,
    ) -> dict[str, Any]:
        """自然语言转 SQL 并执行查询.

        Args:
            question: 自然语言问题
            tenant_id: 当前租户 ID
            db: 数据库会话

        Returns:
            包含 SQL、数据、置信度与执行耗时的字典
        """
        # 生成 SQL
        result = self.backend.generate_sql(question)

        if result.error or not result.sql:
            return {
                "question": question,
                "sql": None,
                "data": [],
                "execution_time_ms": 0,
                "confidence": 0.0,
                "backend": result.backend,
                "error": result.error or "无法生成 SQL",
            }

        # 注入租户 ID
        sql = result.sql.replace(":tenant_id", f"'{tenant_id}'")

        # 沙箱校验
        try:
            self.sandbox.validate(sql)
        except SQLSandboxError as exc:
            return {
                "question": question,
                "sql": sql,
                "data": [],
                "execution_time_ms": 0,
                "confidence": 0.0,
                "backend": result.backend,
                "error": f"SQL sandbox rejected: {exc!s}",
            }

        # 执行查询
        start = time.perf_counter()
        try:
            rows = db.execute(text(sql)).mappings().all()
            data = [dict(row) for row in rows]
        except Exception as exc:  # noqa: BLE001
            return {
                "question": question,
                "sql": sql,
                "data": [],
                "execution_time_ms": int((time.perf_counter() - start) * 1000),
                "confidence": 0.0,
                "backend": result.backend,
                "error": f"Execution failed: {exc!s}",
            }

        execution_time_ms = int((time.perf_counter() - start) * 1000)

        return {
            "question": question,
            "sql": sql,
            "data": data,
            "execution_time_ms": execution_time_ms,
            "confidence": result.confidence,
            "backend": result.backend,
            "explanation": result.explanation,
        }
