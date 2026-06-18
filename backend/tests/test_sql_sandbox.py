"""SQL 沙箱校验测试."""

import pytest

from app.text2sql.sql_sandbox import SQLSandbox, SQLSandboxError


def test_allow_select() -> None:
    """允许合法 SELECT."""
    sandbox = SQLSandbox(allowed_tables=["financial_reports"])
    sandbox.validate("SELECT net_profit FROM financial_reports WHERE year = 2025")


def test_reject_non_select() -> None:
    """拒绝非 SELECT 语句."""
    sandbox = SQLSandbox()
    with pytest.raises(SQLSandboxError, match="Only SELECT statements"):
        sandbox.validate("DELETE FROM financial_reports")


def test_reject_forbidden_keyword() -> None:
    """拒绝危险关键字."""
    sandbox = SQLSandbox()
    with pytest.raises(SQLSandboxError, match="Forbidden keyword"):
        sandbox.validate("SELECT * FROM financial_reports; DROP TABLE users")


def test_reject_disallowed_table() -> None:
    """拒绝不在白名单的表."""
    sandbox = SQLSandbox(allowed_tables=["financial_reports"])
    with pytest.raises(SQLSandboxError, match="Disallowed tables"):
        sandbox.validate("SELECT * FROM secret_table")
