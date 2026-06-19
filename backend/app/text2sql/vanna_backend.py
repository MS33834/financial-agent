"""基于 Vanna 的 Text2SQL 后端（可选）.

Vanna 需要额外安装 ``pip install -e '.[ai]'`` 并配置 Ollama/Chroma。
若未安装或未训练，则自动降级到规则后端。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.logger import get_logger
from app.text2sql.base import NL2SQLResult, Text2SQLBackend
from app.text2sql.rule_backend import RuleBasedText2SQLBackend

if TYPE_CHECKING:
    from vanna.base import VannaBase

logger = get_logger(__name__)


class VannaText2SQLBackend(Text2SQLBackend):
    """Vanna NL2SQL 后端.

    使用本地 Ollama + Chroma 实现 RAG-based Text2SQL。
    当 Vanna 不可用时，降级为规则后端。
    """

    name = "vanna"

    def __init__(self, model: str = "qwen2.5:7b", host: str = "http://fa-ollama:11434") -> None:
        """初始化 Vanna 后端.

        Args:
            model: Ollama 模型名。
            host: Ollama 服务地址。
        """
        self.model = model
        self.host = host
        self._fallback = RuleBasedText2SQLBackend()
        self._vn: VannaBase | None = None

    def generate_sql(self, question: str) -> NL2SQLResult:
        """使用 Vanna 生成 SQL，失败时降级到规则后端."""
        vn = self._get_vanna()
        if vn is None:
            logger.warning("vanna_unavailable_fallback_to_rule", question=question)
            return self._fallback.generate_sql(question)

        try:
            sql = vn.generate_sql(question)
            if not sql or not isinstance(sql, str):
                return self._fallback.generate_sql(question)

            return NL2SQLResult(
                sql=sql,
                confidence=0.85,
                backend=self.name,
                explanation="Vanna 基于训练数据生成 SQL",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("vanna_generate_failed", error=str(exc), question=question)
            return self._fallback.generate_sql(question)

    def _get_vanna(self) -> VannaBase | None:
        """延迟初始化 Vanna 客户端."""
        if self._vn is not None:
            return self._vn

        try:
            from vanna.chromadb import ChromaDB_VectorStore
            from vanna.ollama import Ollama
        except ImportError:
            logger.warning("vanna_package_not_installed")
            return None

        try:

            class FinancialVanna(ChromaDB_VectorStore, Ollama):  # type: ignore[misc]
                def __init__(self, config: dict[str, Any] | None = None) -> None:
                    super().__init__(config=config)

            vn = FinancialVanna(
                config={
                    "model": self.model,
                    "ollama_host": self.host,
                }
            )
            self._vn = vn
            return vn
        except Exception as exc:  # noqa: BLE001
            logger.warning("vanna_init_failed", error=str(exc))
            return None
