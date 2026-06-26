"""Vanna Text2SQL 引擎模块.

封装 Vanna（RAG-based NL2SQL）的训练与 SQL 生成能力，作为可选的 Text2SQL 引擎层。
未安装 vanna 时引擎不可用，调用方应降级到规则后端。
"""

from vanna_engine.engine import VannaEngine, VannaEngineError, is_available

__all__ = [
    "VannaEngine",
    "VannaEngineError",
    "is_available",
]
