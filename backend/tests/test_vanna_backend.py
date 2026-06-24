"""Vanna Text2SQL 后端测试."""

from unittest.mock import MagicMock, patch

from app.text2sql.base import NL2SQLResult
from app.text2sql.vanna_backend import VannaText2SQLBackend


class TestVannaText2SQLBackend:
    """VannaText2SQLBackend 测试."""

    def test_init_sets_config(self) -> None:
        """初始化应保存模型与主机配置."""
        backend = VannaText2SQLBackend(model="qwen2.5:3b", host="http://ollama:11434")
        assert backend.model == "qwen2.5:3b"
        assert backend.host == "http://ollama:11434"
        assert backend.name == "vanna"

    def test_generate_sql_fallback_when_vanna_not_installed(self) -> None:
        """未安装 vanna 包时应降级到规则后端."""
        backend = VannaText2SQLBackend()
        with patch.object(backend._fallback, "generate_sql") as mock_fallback:
            mock_fallback.return_value = NL2SQLResult(
                sql="SELECT 1",
                confidence=0.5,
                backend="rule",
                explanation="fallback",
            )
            with patch.dict("sys.modules", {"vanna.chromadb": None, "vanna.ollama": None}):
                result = backend.generate_sql("今年收入是多少")

        assert result.sql == "SELECT 1"
        assert result.backend == "rule"

    def test_generate_sql_fallback_on_init_error(self) -> None:
        """Vanna 初始化失败时应降级到规则后端."""
        backend = VannaText2SQLBackend()
        with patch.object(backend._fallback, "generate_sql") as mock_fallback:
            mock_fallback.return_value = NL2SQLResult(
                sql="SELECT 2",
                confidence=0.5,
                backend="rule",
                explanation="fallback",
            )

            mock_vn_class = self._build_vanna_class(init_raises=RuntimeError("init failed"))
            chromadb_mod = MagicMock()
            chromadb_mod.ChromaDB_VectorStore = mock_vn_class
            ollama_mod = MagicMock()
            ollama_mod.Ollama = object

            with patch.dict(
                "sys.modules",
                {"vanna.chromadb": chromadb_mod, "vanna.ollama": ollama_mod},
            ):
                result = backend.generate_sql("query")

        assert result.sql == "SELECT 2"
        assert result.backend == "rule"

    def test_generate_sql_returns_vanna_result(self) -> None:
        """Vanna 正常生成 SQL 时返回 Vanna 结果."""
        backend = VannaText2SQLBackend()
        mock_vn = MagicMock()
        mock_vn.generate_sql.return_value = "SELECT revenue FROM reports WHERE year = 2024"

        with patch.object(backend, "_get_vanna", return_value=mock_vn):
            result = backend.generate_sql("2024年收入")

        assert result.sql == "SELECT revenue FROM reports WHERE year = 2024"
        assert result.confidence == 0.85
        assert result.backend == "vanna"

    def test_generate_sql_fallback_on_empty_result(self) -> None:
        """Vanna 返回空 SQL 时降级到规则后端."""
        backend = VannaText2SQLBackend()
        mock_vn = MagicMock()
        mock_vn.generate_sql.return_value = ""

        with (
            patch.object(backend, "_get_vanna", return_value=mock_vn),
            patch.object(backend._fallback, "generate_sql") as mock_fallback,
        ):
            mock_fallback.return_value = NL2SQLResult(
                sql="SELECT 3",
                confidence=0.5,
                backend="rule",
                explanation="fallback",
            )
            result = backend.generate_sql("query")

        assert result.sql == "SELECT 3"
        assert result.backend == "rule"

    def test_generate_sql_fallback_on_non_string_result(self) -> None:
        """Vanna 返回非字符串 SQL 时降级到规则后端."""
        backend = VannaText2SQLBackend()
        mock_vn = MagicMock()
        mock_vn.generate_sql.return_value = ["SELECT 4"]

        with (
            patch.object(backend, "_get_vanna", return_value=mock_vn),
            patch.object(backend._fallback, "generate_sql") as mock_fallback,
        ):
            mock_fallback.return_value = NL2SQLResult(
                sql="SELECT 4",
                confidence=0.5,
                backend="rule",
                explanation="fallback",
            )
            result = backend.generate_sql("query")

        assert result.sql == "SELECT 4"
        assert result.backend == "rule"

    def test_generate_sql_fallback_on_exception(self) -> None:
        """Vanna 生成异常时降级到规则后端."""
        backend = VannaText2SQLBackend()
        mock_vn = MagicMock()
        mock_vn.generate_sql.side_effect = RuntimeError("model error")

        with (
            patch.object(backend, "_get_vanna", return_value=mock_vn),
            patch.object(backend._fallback, "generate_sql") as mock_fallback,
        ):
            mock_fallback.return_value = NL2SQLResult(
                sql="SELECT 5",
                confidence=0.5,
                backend="rule",
                explanation="fallback",
            )
            result = backend.generate_sql("query")

        assert result.sql == "SELECT 5"
        assert result.backend == "rule"

    def test_get_vanna_cached(self) -> None:
        """Vanna 实例应被缓存."""
        backend = VannaText2SQLBackend()
        mock_vn = MagicMock()
        backend._vn = mock_vn

        assert backend._get_vanna() is mock_vn

    @staticmethod
    def _build_vanna_class(init_raises: Exception | None = None) -> type:
        """构造模拟的 Vanna 基类."""

        class FakeChromaDB:
            def __init__(self, _config: dict[str, object] | None = None) -> None:
                if init_raises is not None:
                    raise init_raises

        return FakeChromaDB
