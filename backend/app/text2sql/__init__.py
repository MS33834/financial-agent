"""Text2SQL 模块.

提供可插拔的自然语言转 SQL 后端与 SQL 沙箱校验。
"""

from app.text2sql.base import NL2SQLResult, Text2SQLBackend
from app.text2sql.rule_backend import RuleBasedText2SQLBackend
from app.text2sql.sql_sandbox import SQLSandbox

__all__ = [
    "NL2SQLResult",
    "Text2SQLBackend",
    "RuleBasedText2SQLBackend",
    "SQLSandbox",
]
