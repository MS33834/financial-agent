"""基于 Ollama embeddings 的轻量 RAG 服务.

数据按 tenant_id + document_id 存储在内存索引中，适合 MVP 阶段单节点部署。
"""

from __future__ import annotations

import json
import math
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import engine


class RagUnavailableError(Exception):
    """RAG 服务（Ollama embeddings）不可用异常."""

    pass


def chunk_text(text: str, chunk_size: int) -> list[str]:
    """按段落与长度切分文本.

    Args:
        text: 待切分长文本。
        chunk_size: 每个 chunk 的最大字符数。

    Returns:
        切分后的文本片段列表。
    """
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 1 <= chunk_size:
            current = f"{current}\n{para}".strip() if current else para
        else:
            if current:
                chunks.append(current)
            # 长段落按 chunk_size 截断
            while len(para) > chunk_size:
                chunks.append(para[:chunk_size])
                para = para[chunk_size:]
            current = para

    if current:
        chunks.append(current)

    return chunks


def embed(text: str) -> list[float]:
    """调用 Ollama /api/embeddings 获取文本向量.

    Args:
        text: 待编码文本。

    Returns:
        浮点数向量。

    Raises:
        RagUnavailableError: 当 Ollama 不可达或返回异常时抛出。
    """
    settings = get_settings()
    url = f"{settings.ollama_host.rstrip('/')}/api/embeddings"
    payload = {
        "model": settings.ollama_model,
        "prompt": text,
    }
    try:
        response = httpx.post(url, json=payload, timeout=30.0)
    except Exception as exc:  # noqa: BLE001
        raise RagUnavailableError(f"无法连接到 Ollama embeddings: {exc!s}") from exc

    if response.status_code != 200:
        raise RagUnavailableError(
            f"Ollama embeddings 返回 {response.status_code}: {response.text[:200]}"
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise RagUnavailableError(f"Ollama embeddings 返回非 JSON: {exc!s}") from exc

    embedding = data.get("embedding")
    if not isinstance(embedding, list):
        raise RagUnavailableError("Ollama embeddings 返回格式异常，缺少 embedding 字段")
    return [float(x) for x in embedding]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度（纯 Python，不依赖 numpy）."""
    if len(a) != len(b):
        raise ValueError("向量维度不一致")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# rag_chunks 表建表语句（兼容 PostgreSQL 与 SQLite）
_CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS rag_chunks (
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk TEXT NOT NULL,
    embedding TEXT NOT NULL,
    PRIMARY KEY (tenant_id, document_id, chunk_index)
)
"""


class RagService:
    """轻量 RAG 服务：切分、嵌入、检索."""

    def __init__(self) -> None:
        """初始化空索引."""
        # key: (tenant_id, document_id) -> list of {"chunk": str, "embedding": list[float]}
        self._index: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def index_document(
        self,
        document_id: str,
        text: str,
        tenant_id: str = "",
    ) -> None:
        """为指定文档建立索引.

        Args:
            document_id: 文档 ID。
            text: 文档原始文本。
            tenant_id: 租户 ID，用于索引隔离。
        """
        settings = get_settings()
        chunks = chunk_text(text, settings.rag_chunk_size)
        entries = []
        for chunk in chunks:
            embedding = embed(chunk)
            entries.append({"chunk": chunk, "embedding": embedding})
        self._index[(tenant_id, document_id)] = entries
        # M5: 持久化到数据库（增强层，失败不影响内存索引）
        self._persist_chunks(tenant_id, document_id, entries)

    def query(
        self,
        question: str,
        tenant_id: str,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        """检索相关文本片段并返回答案.

        Args:
            question: 用户问题。
            tenant_id: 租户 ID，用于数据隔离。
            document_id: 指定文档 ID，None 则搜索该租户下全部索引文档。

        Returns:
            {"answer": "...", "chunks": [...], "document_id": "..."}

        Raises:
            RagUnavailableError: embeddings 不可用时抛出。
            ValueError: 未找到可检索文档时抛出。
        """
        settings = get_settings()
        question_embedding = embed(question)

        candidates: list[tuple[str, dict[str, Any]]] = []
        if document_id is not None:
            key = (tenant_id, document_id)
            if key in self._index:
                candidates = [(document_id, entry) for entry in self._index[key]]
            else:
                # M5: 内存索引未命中，回退查询数据库
                candidates = self._query_db(tenant_id, document_id)
                if not candidates:
                    raise ValueError(f"文档 {document_id} 尚未建立索引")
        else:
            for (doc_tenant, doc_id), entries in self._index.items():
                if doc_tenant != tenant_id:
                    continue
                for entry in entries:
                    candidates.append((doc_id, entry))
            # M5: 内存索引未命中，回退查询数据库
            if not candidates:
                candidates = self._query_db(tenant_id, None)

        if not candidates:
            raise ValueError("未找到可检索的文档索引")

        scored = []
        for doc_id, entry in candidates:
            score = cosine_similarity(question_embedding, entry["embedding"])
            scored.append((score, doc_id, entry["chunk"]))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_k = scored[: settings.rag_top_k]

        chunks = [chunk for _score, _doc_id, chunk in top_k]
        best_doc_id = top_k[0][1] if top_k else (document_id or "")
        answer = "根据文档内容：\n" + "\n".join(f"- {chunk}" for chunk in chunks)

        return {
            "answer": answer,
            "chunks": chunks,
            "document_id": best_doc_id,
        }

    def _ensure_table(self) -> None:
        """确保 rag_chunks 表存在（幂等操作）。"""
        with engine.connect() as conn:
            conn.execute(text(_CREATE_TABLE_SQL))
            conn.commit()

    def _persist_chunks(
        self,
        tenant_id: str,
        document_id: str,
        entries: list[dict[str, Any]],
    ) -> None:
        """将 chunk 数据写入数据库（增强层，失败不影响内存索引）。"""
        try:
            self._ensure_table()
            with engine.connect() as conn:
                # 先删除该文档的旧索引
                conn.execute(
                    text(
                        "DELETE FROM rag_chunks "
                        "WHERE tenant_id = :tenant AND document_id = :doc"
                    ),
                    {"tenant": tenant_id, "doc": document_id},
                )
                for idx, entry in enumerate(entries):
                    conn.execute(
                        text(
                            "INSERT INTO rag_chunks "
                            "(tenant_id, document_id, chunk_index, chunk, embedding) "
                            "VALUES (:tenant, :doc, :idx, :chunk, :embedding)"
                        ),
                        {
                            "tenant": tenant_id,
                            "doc": document_id,
                            "idx": idx,
                            "chunk": entry["chunk"],
                            "embedding": json.dumps(entry["embedding"]),
                        },
                    )
                conn.commit()
        except Exception:
            # 持久化失败不影响主流程，内存索引仍可用
            pass

    def _query_db(
        self,
        tenant_id: str,
        document_id: str | None,
    ) -> list[tuple[str, dict[str, Any]]]:
        """从数据库查询 chunk（内存索引未命中时的回退）。"""
        candidates: list[tuple[str, dict[str, Any]]] = []
        try:
            self._ensure_table()
            with engine.connect() as conn:
                if document_id is not None:
                    rows = conn.execute(
                        text(
                            "SELECT document_id, chunk, embedding FROM rag_chunks "
                            "WHERE tenant_id = :tenant AND document_id = :doc"
                        ),
                        {"tenant": tenant_id, "doc": document_id},
                    ).fetchall()
                else:
                    rows = conn.execute(
                        text(
                            "SELECT document_id, chunk, embedding FROM rag_chunks "
                            "WHERE tenant_id = :tenant"
                        ),
                        {"tenant": tenant_id},
                    ).fetchall()
                for row in rows:
                    doc_id = str(row[0])
                    chunk = str(row[1])
                    embedding = [float(x) for x in json.loads(row[2])]
                    candidates.append((doc_id, {"chunk": chunk, "embedding": embedding}))
        except Exception:
            # 数据库查询失败不影响主流程
            pass
        return candidates

    def persist_to_db(self, db: Session) -> None:
        """将内存索引持久化到数据库。

        Args:
            db: 数据库会话，由调用方管理生命周期与提交。
        """
        db.execute(text(_CREATE_TABLE_SQL))
        for (tenant_id, document_id), entries in self._index.items():
            db.execute(
                text(
                    "DELETE FROM rag_chunks "
                    "WHERE tenant_id = :tenant AND document_id = :doc"
                ),
                {"tenant": tenant_id, "doc": document_id},
            )
            for idx, entry in enumerate(entries):
                db.execute(
                    text(
                        "INSERT INTO rag_chunks "
                        "(tenant_id, document_id, chunk_index, chunk, embedding) "
                        "VALUES (:tenant, :doc, :idx, :chunk, :embedding)"
                    ),
                    {
                        "tenant": tenant_id,
                        "doc": document_id,
                        "idx": idx,
                        "chunk": entry["chunk"],
                        "embedding": json.dumps(entry["embedding"]),
                    },
                )
        db.commit()
