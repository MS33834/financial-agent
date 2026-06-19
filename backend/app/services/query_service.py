"""自然语言查询服务."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User
from app.services.audit_service import log_action
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
        user: User | None = None,
    ) -> dict[str, Any]:
        """自然语言转 SQL 并执行查询.

        Args:
            question: 自然语言问题
            tenant_id: 当前租户 ID
            db: 数据库会话
            user: 当前用户，用于审计；可选

        Returns:
            包含 SQL、数据、置信度与执行耗时的字典
        """

        def _truncate_reason(text: str, max_len: int = 200) -> str:
            """截断审计 reason 避免过长."""
            return text if len(text) <= max_len else text[:max_len] + "..."

        # 生成 SQL
        gen_result = self.backend.generate_sql(question)

        if gen_result.error or not gen_result.sql:
            error = gen_result.error or "无法生成 SQL"
            response: dict[str, Any] = {
                "question": question,
                "sql": None,
                "data": [],
                "execution_time_ms": 0,
                "confidence": 0.0,
                "backend": gen_result.backend,
                "error": error,
            }
            log_action(
                db=db,
                action="queries.nl2sql",
                resource=f"query://{tenant_id}",
                result="failed",
                user=user,
                reason=_truncate_reason(f"question={question}, error={error}"),
            )
            return response

        # 注入租户 ID
        sql = gen_result.sql.replace(":tenant_id", f"'{tenant_id}'")

        # 沙箱校验
        try:
            self.sandbox.validate(sql)
        except SQLSandboxError as exc:
            error = f"SQL sandbox rejected: {exc!s}"
            response = {
                "question": question,
                "sql": sql,
                "data": [],
                "execution_time_ms": 0,
                "confidence": 0.0,
                "backend": gen_result.backend,
                "error": error,
            }
            log_action(
                db=db,
                action="queries.nl2sql",
                resource=f"query://{tenant_id}",
                result="failed",
                user=user,
                reason=_truncate_reason(f"question={question}, error={error}"),
            )
            return response

        # 执行查询
        start = time.perf_counter()
        try:
            rows = db.execute(text(sql)).mappings().all()
            data = [dict(row) for row in rows]
        except Exception as exc:  # noqa: BLE001
            error = f"Execution failed: {exc!s}"
            response = {
                "question": question,
                "sql": sql,
                "data": [],
                "execution_time_ms": int((time.perf_counter() - start) * 1000),
                "confidence": 0.0,
                "backend": gen_result.backend,
                "error": error,
            }
            log_action(
                db=db,
                action="queries.nl2sql",
                resource=f"query://{tenant_id}",
                result="failed",
                user=user,
                reason=_truncate_reason(f"question={question}, error={error}"),
            )
            return response

        execution_time_ms = int((time.perf_counter() - start) * 1000)

        response = {
            "question": question,
            "sql": sql,
            "data": data,
            "execution_time_ms": execution_time_ms,
            "confidence": gen_result.confidence,
            "backend": gen_result.backend,
            "explanation": gen_result.explanation,
        }
        log_action(
            db=db,
            action="queries.nl2sql",
            resource=f"query://{tenant_id}",
            result="success",
            user=user,
            reason=_truncate_reason(f"question={question}, backend={gen_result.backend}"),
        )
        return response
