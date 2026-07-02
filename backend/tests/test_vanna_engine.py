"""vanna_engine 引擎模块测试."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vanna_engine import VannaEngine, VannaEngineError, is_available


def _patched_engine(monkeypatch: pytest.MonkeyPatch, client: MagicMock | None = None) -> VannaEngine:
    """构造一个绕过 vanna 安装检查的引擎，并注入 mock 客户端."""
    monkeypatch.setattr(VannaEngine, "_check_installed", staticmethod(lambda: True))
    engine = VannaEngine()
    if client is not None:
        monkeypatch.setattr(engine, "_get_client", lambda: client)
    return engine


def test_is_available_false_when_vanna_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(VannaEngine, "_check_installed", staticmethod(lambda: False))
    engine = VannaEngine()
    assert engine.is_available is False


def test_generate_sql_raises_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(VannaEngine, "_check_installed", staticmethod(lambda: False))
    engine = VannaEngine()
    with pytest.raises(VannaEngineError):
        engine.generate_sql("select 1")


def test_train_ddl_delegates_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    engine = _patched_engine(monkeypatch, client)
    engine.train_ddl("CREATE TABLE t (id int)")
    client.train.assert_called_once_with(ddl="CREATE TABLE t (id int)")


def test_train_sql_with_question(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    engine = _patched_engine(monkeypatch, client)
    engine.train_sql("SELECT 1", question="how many")
    client.train.assert_called_once_with(sql="SELECT 1", question="how many")


def test_train_sql_without_question(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    engine = _patched_engine(monkeypatch, client)
    engine.train_sql("SELECT 1")
    client.train.assert_called_once_with(sql="SELECT 1")


def test_train_documentation_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    engine = _patched_engine(monkeypatch, client)
    engine.train_documentation("净利润指...")
    client.train.assert_called_once_with(documentation="净利润指...")


def test_generate_sql_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.generate_sql.return_value = "SELECT revenue FROM financial_reports"
    engine = _patched_engine(monkeypatch, client)
    assert engine.generate_sql("营收") == "SELECT revenue FROM financial_reports"
    client.generate_sql.assert_called_once_with(question="营收")


def test_generate_sql_returns_none_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.generate_sql.side_effect = RuntimeError("boom")
    engine = _patched_engine(monkeypatch, client)
    assert engine.generate_sql("营收") is None


def test_generate_sql_returns_none_on_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.generate_sql.return_value = "   "
    engine = _patched_engine(monkeypatch, client)
    assert engine.generate_sql("营收") is None


def test_generate_sql_returns_none_on_non_string(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.generate_sql.return_value = 123
    engine = _patched_engine(monkeypatch, client)
    assert engine.generate_sql("营收") is None


def test_get_training_data_returns_records(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    df = MagicMock()
    df.to_dict.return_value = [{"id": "1", "type": "ddl"}]
    client.get_training_data.return_value = df
    engine = _patched_engine(monkeypatch, client)
    assert engine.get_training_data() == [{"id": "1", "type": "ddl"}]
    df.to_dict.assert_called_once_with(orient="records")


def test_get_training_data_empty_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    df = MagicMock()
    df.to_dict.side_effect = RuntimeError("x")
    client.get_training_data.return_value = df
    engine = _patched_engine(monkeypatch, client)
    assert engine.get_training_data() == []


def test_remove_training_data_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    engine = _patched_engine(monkeypatch, client)
    assert engine.remove_training_data("id1") is True
    client.remove_training_data.assert_called_once_with(id="id1")


def test_remove_training_data_false_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.remove_training_data.side_effect = RuntimeError("x")
    engine = _patched_engine(monkeypatch, client)
    assert engine.remove_training_data("id1") is False


def test_reset_clears_client(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _patched_engine(monkeypatch)
    engine._client = MagicMock()  # 模拟已初始化
    engine.reset()
    assert engine._client is None
    assert engine._checked_available is False
    assert engine._available is False


def test_is_available_module_function(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(VannaEngine, "_check_installed", staticmethod(lambda: True))
    assert is_available() is True
    monkeypatch.setattr(VannaEngine, "_check_installed", staticmethod(lambda: False))
    assert is_available() is False


def test_engine_config_stored() -> None:
    engine = VannaEngine(
        model="qwen3:8b",
        ollama_host="http://ollama:11434",
        chroma_persist_dir="/data/chroma",
    )
    assert engine.model == "qwen3:8b"
    assert engine.ollama_host == "http://ollama:11434"
    assert engine.chroma_persist_dir == "/data/chroma"
