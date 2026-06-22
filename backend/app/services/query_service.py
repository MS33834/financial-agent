"""自然语言查询服务."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.logger import get_logger
from app.models.user import User
from app.services.audit_service import log_action
from app.text2sql.base import Text2SQLBackend
from app.text2sql.rule_backend import RuleBasedText2SQLBackend
from app.text2sql.sql_sandbox import SQLSandbox, SQLSandboxError

logger = get_logger(__name__)


class QueryService:
    """自然语言查询服务。"""

    def __init__(self, backend: Text2SQLBackend | None = None) -> None:
        self.backend = backend or self._default_backend()
        self.sandbox = SQLSandbox(
            allowed_tables=["financial_reports", "accounts", "vouchers"],
        )

    @staticmethod
    def _default_backend() -> Text2SQLBackend:
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
        def truncate(text: str, max_len: int = 200) -> str:
            return text if len(text) <= max_len else text[:max_len] + "..."

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
                reason=truncate(f"question={question}, error={error}"),
            )
            return response

        sql = gen_result.sql

        try:
            self.sandbox.validate(sql)
        except SQLSandboxError as exc:
            logger.warning(
                "nl2sql_sandbox_rejected",
                tenant_id=tenant_id,
                question=question,
                sql=sql,
                reason=str(exc),
            )
            response = {
                "question": question,
                "sql": sql,
                "data": [],
                "execution_time_ms": 0,
                "confidence": 0.0,
                "backend": gen_result.backend,
                "error": "该问题无法通过安全校验，请避免涉及非财务数据表或敏感操作",
            }
            log_action(
                db=db,
                action="queries.nl2sql",
                resource=f"query://{tenant_id}",
                result="failed",
                user=user,
                reason=truncate(f"question={question}, error={exc!s}"),
            )
            return response

        # 执行查询
        start = time.perf_counter()
        try:
            rows = db.execute(text(sql), {"tenant_id": tenant_id}).mappings().all()
            data = [dict(row) for row in rows]
        except SQLAlchemyError as exc:
            logger.warning(
                "nl2sql_execution_failed",
                tenant_id=tenant_id,
                question=question,
                sql=sql,
                error=str(exc),
            )
            response = {
                "question": question,
                "sql": sql,
                "data": [],
                "execution_time_ms": int((time.perf_counter() - start) * 1000),
                "confidence": 0.0,
                "backend": gen_result.backend,
                "error": "查询执行失败，请换一种问法或联系管理员",
            }
            log_action(
                db=db,
                action="queries.nl2sql",
                resource=f"query://{tenant_id}",
                result="failed",
                user=user,
                reason=truncate(f"question={question}, error={exc!s}"),
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
            reason=truncate(f"question={question}, backend={gen_result.backend}"),
        )
        return response
