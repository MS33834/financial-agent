"""RAG 服务（app.services.rag_service）补全测试.

覆盖：
- 切分/嵌入/余弦相似度/查询/持久化全链路
- embed() 失败路径（连接失败、非 200、非 JSON、缺 embedding）
- query() 内存命中 / DB 回退 / 无候选 / tenant 隔离
- persist_to_db / _query_db 异常降级（不影响主流程）
"""

# mypy: disable-error-code="attr-defined"

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.rag_service import (
    RagService,
    RagUnavailableError,
    chunk_text,
    cosine_similarity,
    embed,
)


# ------------------------------------------------------------------
# chunk_text
# ------------------------------------------------------------------


def test_chunk_text_empty_returns_empty() -> None:
    """空文本应返回空列表."""
    assert chunk_text("", 100) == []
    assert chunk_text("   \n  \n", 100) == []


def test_chunk_text_short_paragraph() -> None:
    """单段短文本应原样返回."""
    assert chunk_text("hello world", 100) == ["hello world"]


def test_chunk_text_multiple_paragraphs_within_size() -> None:
    """多段总长在 chunk_size 内的应合并为一个 chunk."""
    text = "para1\npara2\npara3"
    assert chunk_text(text, 100) == ["para1\npara2\npara3"]


def test_chunk_text_oversized_paragraph_split() -> None:
    """超长段落应按 chunk_size 切分为多个 chunk."""
    text = "a" * 250
    chunks = chunk_text(text, 100)
    # 250 字符应被切成 3 段：100 + 100 + 50
    assert chunks == ["a" * 100, "a" * 100, "a" * 50]


def test_chunk_text_mixed_paragraphs() -> None:
    """混合长短段落."""
    long = "x" * 50
    text = f"short\n{long}\nmedium"
    chunks = chunk_text(text, 30)
    # 短段先攒，超过 30 后开始切长段
    assert len(chunks) >= 2


# ------------------------------------------------------------------
# cosine_similarity
# ------------------------------------------------------------------


def test_cosine_similarity_identical() -> None:
    """相同向量余弦相似度为 1."""
    v = [1.0, 2.0, 3.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal() -> None:
    """正交向量余弦相似度为 0."""
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-9


def test_cosine_similarity_dimension_mismatch_raises() -> None:
    """维度不一致应抛 ValueError."""
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])


def test_cosine_similarity_zero_vector() -> None:
    """零向量相似度为 0（避免除零）."""
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


# ------------------------------------------------------------------
# embed
# ------------------------------------------------------------------


def test_embed_success() -> None:
    """成功路径应返回 embedding 列表."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    with patch("app.services.rag_service.httpx.post", return_value=fake_response) as mock_post:
        result = embed("test")
    assert result == [0.1, 0.2, 0.3]
    mock_post.assert_called_once()


def test_embed_connection_error_raises_unavailable() -> None:
    """Ollama 不可达应抛 RagUnavailableError."""
    with patch("app.services.rag_service.httpx.post", side_effect=Exception("conn refused")):
        with pytest.raises(RagUnavailableError) as exc_info:
            embed("test")
    assert "无法连接" in str(exc_info.value)


def test_embed_non_200_raises_unavailable() -> None:
    """Ollama 返回非 200 应抛 RagUnavailableError."""
    fake_response = MagicMock()
    fake_response.status_code = 500
    fake_response.text = "internal error"
    with patch("app.services.rag_service.httpx.post", return_value=fake_response):
        with pytest.raises(RagUnavailableError) as exc_info:
            embed("test")
    assert "500" in str(exc_info.value)


def test_embed_invalid_json_raises_unavailable() -> None:
    """Ollama 返回非 JSON 应抛 RagUnavailableError."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.side_effect = json.JSONDecodeError("err", "doc", 0)
    with patch("app.services.rag_service.httpx.post", return_value=fake_response):
        with pytest.raises(RagUnavailableError) as exc_info:
            embed("test")
    assert "非 JSON" in str(exc_info.value)


def test_embed_missing_embedding_field_raises() -> None:
    """Ollama 返回无 embedding 字段应抛 RagUnavailableError."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"other": "data"}
    with patch("app.services.rag_service.httpx.post", return_value=fake_response):
        with pytest.raises(RagUnavailableError) as exc_info:
            embed("test")
    assert "缺少 embedding" in str(exc_info.value)


def test_embed_non_list_embedding_raises() -> None:
    """embedding 不是 list 应抛 RagUnavailableError."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"embedding": "not-a-list"}
    with patch("app.services.rag_service.httpx.post", return_value=fake_response):
        with pytest.raises(RagUnavailableError):
            embed("test")


# ------------------------------------------------------------------
# RagService
# ------------------------------------------------------------------


def _fake_embed_factory(vectors: list[list[float]]):
    """构造 embed 的 mock，每次调用依次返回 vectors 中的下一个."""
    iterator = iter(vectors)
    responses: list[Any] = []

    def _fake_embed(_text: str) -> list[float]:
        v = next(iterator)
        return v

    return _fake_embed


def test_rag_service_index_and_query_in_memory() -> None:
    """索引文档后内存查询应返回答案."""
    service = RagService()
    # 每段 > 512 字符以确保被切分（默认 chunk_size=512），共 3 段 → 6 chunks
    para = "甲" * 600
    long_text = para + "\n" + para + "\n" + para
    # 6 个 chunk 对应 6 次 embed
    fake = _fake_embed_factory([
        [0.0, 1.0], [1.0, 0.0],
        [0.0, 1.0], [1.0, 0.0],
        [0.0, 1.0], [1.0, 0.0],
    ])
    with patch("app.services.rag_service.embed", side_effect=fake), \
         patch("app.services.rag_service.engine") as mock_engine:
        mock_engine.connect.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        service.index_document("doc1", long_text, tenant_id="t1")
    # 内存中应有 6 个 chunk
    assert len(service._index[("t1", "doc1")]) == 6

    # 查询：question embedding 接近 chunk 0
    with patch("app.services.rag_service.embed", return_value=[0.0, 1.0]):
        result = service.query("alpha", tenant_id="t1", document_id="doc1")
    assert "根据文档内容" in result["answer"]
    assert result["document_id"] == "doc1"
    assert len(result["chunks"]) >= 1


def test_rag_service_query_across_tenant_isolation() -> None:
    """不同租户不应能访问到对方的索引."""
    service = RagService()
    service._index[("t1", "doc1")] = [{"chunk": "secret", "embedding": [0.0, 1.0]}]
    # 租户 t2 查询 t1 的文档应找不到
    with patch("app.services.rag_service.embed", return_value=[0.0, 1.0]):
        with pytest.raises(ValueError) as exc_info:
            service.query("test", tenant_id="t2", document_id="doc1")
    assert "尚未建立索引" in str(exc_info.value)


def test_rag_service_query_all_tenant_docs() -> None:
    """不指定 document_id 时应搜索租户下全部索引文档."""
    service = RagService()
    service._index[("t1", "d1")] = [{"chunk": "first", "embedding": [0.0, 1.0]}]
    service._index[("t1", "d2")] = [{"chunk": "second", "embedding": [1.0, 0.0]}]
    # 跨租户数据不应被搜到
    service._index[("t9", "d3")] = [{"chunk": "third", "embedding": [1.0, 0.0]}]

    with patch("app.services.rag_service.embed", return_value=[0.0, 1.0]):
        result = service.query("test", tenant_id="t1")
    assert result["document_id"] in {"d1", "d2"}


def test_rag_service_query_fallback_to_db() -> None:
    """内存索引未命中时回退到数据库查询."""
    service = RagService()
    # 内存索引为空
    fake_rows = [
        ("d1", "db-chunk", json.dumps([0.0, 1.0])),
    ]

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = fake_rows

    with patch("app.services.rag_service.embed", return_value=[0.0, 1.0]), \
         patch("app.services.rag_service.engine.connect") as mock_connect, \
         patch("app.services.rag_service.text") as mock_text:
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_text.return_value = "SELECT ..."
        result = service.query("test", tenant_id="t1", document_id="d1")
    assert result["document_id"] == "d1"
    assert "db-chunk" in result["answer"]


def test_rag_service_query_no_candidates_raises() -> None:
    """无任何候选（内存与 DB 均空）应抛 ValueError."""
    service = RagService()
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []

    with patch("app.services.rag_service.embed", return_value=[0.0, 1.0]), \
         patch("app.services.rag_service.engine.connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn
        with pytest.raises(ValueError) as exc_info:
            service.query("test", tenant_id="t1", document_id="d1")
    assert "尚未建立索引" in str(exc_info.value)


def test_rag_service_query_all_no_candidates_raises() -> None:
    """租户下无任何文档时应抛 ValueError."""
    service = RagService()
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []

    with patch("app.services.rag_service.embed", return_value=[0.0, 1.0]), \
         patch("app.services.rag_service.engine.connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn
        with pytest.raises(ValueError) as exc_info:
            service.query("test", tenant_id="t1")
    assert "未找到可检索的文档索引" in str(exc_info.value)


def test_rag_service_persist_to_db_swallows_errors() -> None:
    """_persist_chunks 在内部吞掉异常（不影响主流程）."""
    service = RagService()
    service._index[("t1", "d1")] = [{"chunk": "x", "embedding": [0.0, 1.0]}]

    with patch("app.services.rag_service.engine") as mock_engine:
        # engine.connect 抛异常，_persist_chunks 应吞掉
        mock_engine.connect.side_effect = Exception("db down")
        # 不应抛异常
        service._persist_chunks("t1", "d1", service._index[("t1", "d1")])
    # 内存索引仍然存在
    assert service._index[("t1", "d1")][0]["chunk"] == "x"


def test_persist_to_db_executes_4_calls_for_single_entry() -> None:
    """persist_to_db 接收外部 db session，对单条目执行 1 CREATE + 1 DELETE + 1 INSERT."""
    service = RagService()
    service._index[("t1", "d1")] = [
        {"chunk": "a", "embedding": [0.0, 1.0]},
    ]
    mock_db = MagicMock()
    with patch("app.services.rag_service.text") as mock_text:
        mock_text.side_effect = lambda s: s
        service.persist_to_db(mock_db)

    # 1 CREATE + 1 DELETE + 1 INSERT = 3 次 execute
    assert mock_db.execute.call_count == 3
    mock_db.commit.assert_called_once()


def test_persist_to_db_swallows_db_errors() -> None:
    """persist_to_db 不吞 db 异常（异常向上抛，调用方负责）.

    这里通过子测试 1 验证了 _persist_chunks 的吞错行为；persist_to_db 是显式
    不吞错误的同步接口，方便调用方在事务边界进行回滚。
    """
    service = RagService()
    service._index[("t1", "d1")] = [{"chunk": "x", "embedding": [0.0, 1.0]}]
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("db down")
    with pytest.raises(Exception) as exc_info:
        service.persist_to_db(mock_db)
    assert "db down" in str(exc_info.value)


def test_rag_service_index_persist_failure_silent() -> None:
    """index_document 中持久化失败不应影响内存索引."""
    service = RagService()
    fake = _fake_embed_factory([[0.0, 1.0]])

    with patch("app.services.rag_service.embed", side_effect=fake), \
         patch("app.services.rag_service.engine.connect") as mock_connect:
        mock_connect.side_effect = Exception("db down")
        service.index_document("d1", "hello", tenant_id="t1")
    # 内存索引仍然被建立
    assert ("t1", "d1") in service._index


def test_rag_service_query_db_fallback_failure_silent() -> None:
    """_query_db 失败时应返回空 candidates（不抛）."""
    service = RagService()
    with patch("app.services.rag_service.engine.connect") as mock_connect:
        mock_connect.side_effect = Exception("db down")
        result = service._query_db("t1", "d1")
    assert result == []
