"""Vanna Text2SQL 引擎封装.

将 Vanna（基于 RAG 的 NL2SQL）的训练、SQL 生成、训练数据管理能力封装为独立引擎层。
Vanna 为可选依赖（``pip install -e '.[ai]'`` 并配置 Ollama/Chroma），未安装时
引擎标记为不可用，调用方应降级到规则后端（见 ``app.text2sql.rule_backend``）。

与 ``app.text2sql.vanna_backend.VannaText2SQLBackend`` 的关系：
- 本模块是「引擎层」，提供训练 / 查询 / 训练数据管理等原子能力；
- ``VannaText2SQLBackend`` 是「适配层」，将引擎适配到 ``Text2SQLBackend`` 抽象接口，
  并在引擎不可用时自动降级到规则后端。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.logger import get_logger

if TYPE_CHECKING:
    from vanna.base import VannaBase

logger = get_logger(__name__)


class VannaEngineError(RuntimeError):
    """Vanna 引擎不可用或操作失败."""


class VannaEngine:
    """Vanna NL2SQL 引擎.

    使用本地 Ollama + ChromaDB 实现 RAG-based Text2SQL。
    通过训练 DDL / SQL 样例 / 业务文档积累领域知识，进而生成更准确的 SQL。

    典型用法::

        engine = VannaEngine(model="qwen2.5:7b", ollama_host="http://fa-ollama:11434")
        if engine.is_available:
            engine.train_ddl("CREATE TABLE financial_reports (...)")
            sql = engine.generate_sql("2025 年 Q2 净利润是多少")
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        ollama_host: str = "http://fa-ollama:11434",
        chroma_persist_dir: str | Path | None = None,
    ) -> None:
        self.model = model
        self.ollama_host = ollama_host
        self.chroma_persist_dir = str(chroma_persist_dir) if chroma_persist_dir else None
        self._client: VannaBase | None = None
        self._checked_available = False
        self._available = False

    @property
    def is_available(self) -> bool:
        """Vanna 包是否已安装且客户端可初始化（结果会被缓存）."""
        if not self._checked_available:
            self._checked_available = True
            self._available = self._check_installed()
        return self._available

    @staticmethod
    def _check_installed() -> bool:
        """检查 vanna 及其 ChromaDB / Ollama 适配器是否可导入."""
        try:
            import vanna.chromadb  # noqa: F401
            import vanna.ollama  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_client(self) -> VannaBase:
        """延迟初始化并返回 Vanna 客户端，未安装时抛 VannaEngineError."""
        if self._client is not None:
            return self._client
        if not self.is_available:
            raise VannaEngineError(
                "vanna 包未安装，请执行 `pip install -e '.[ai]'` 并配置 Ollama/Chroma 后重试"
            )
        try:
            from vanna.chromadb import ChromaDB_VectorStore
            from vanna.ollama import Ollama

            class FinancialVanna(ChromaDB_VectorStore, Ollama):  # type: ignore[misc]
                def __init__(self, config: dict[str, Any] | None = None) -> None:
                    super().__init__(config=config)

            config: dict[str, Any] = {
                "model": self.model,
                "ollama_host": self.ollama_host,
            }
            if self.chroma_persist_dir:
                config["path"] = self.chroma_persist_dir

            self._client = FinancialVanna(config=config)
            return self._client
        except Exception as exc:  # noqa: BLE001
            raise VannaEngineError(f"Vanna 客户端初始化失败: {exc}") from exc

    def train_ddl(self, ddl: str) -> None:
        """用 DDL 训练引擎，使其学习表结构."""
        self._get_client().train(ddl=ddl)

    def train_sql(self, sql: str, question: str | None = None) -> None:
        """用 SQL 样例训练引擎，可附带对应的自然语言问题."""
        kwargs: dict[str, Any] = {"sql": sql}
        if question:
            kwargs["question"] = question
        self._get_client().train(**kwargs)

    def train_documentation(self, documentation: str) -> None:
        """用业务文档训练引擎，补充领域知识."""
        self._get_client().train(documentation=documentation)

    def generate_sql(self, question: str) -> str | None:
        """根据自然语言生成 SQL。失败或返回空时返回 None."""
        client = self._get_client()
        try:
            sql = client.generate_sql(question=question)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vanna_generate_sql_failed", error=str(exc), question=question)
            return None
        if not isinstance(sql, str) or not sql.strip():
            return None
        return sql

    def get_training_data(self) -> list[dict[str, Any]]:
        """获取已训练的数据条目列表。失败时返回空列表."""
        client = self._get_client()
        df = client.get_training_data()
        try:
            return list(df.to_dict(orient="records"))
        except Exception:  # noqa: BLE001
            return []

    def remove_training_data(self, training_data_id: str) -> bool:
        """按 ID 移除一条训练数据，成功返回 True."""
        client = self._get_client()
        try:
            client.remove_training_data(id=training_data_id)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "vanna_remove_training_data_failed",
                error=str(exc),
                id=training_data_id,
            )
            return False

    def reset(self) -> None:
        """重置引擎，丢弃已初始化的客户端与可用性缓存."""
        self._client = None
        self._checked_available = False
        self._available = False


def is_available() -> bool:
    """模块级便捷函数：检查 vanna 引擎依赖是否可用."""
    return VannaEngine._check_installed()
