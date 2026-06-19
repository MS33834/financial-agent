"""LLM 与 RAG 集成测试."""

from __future__ import annotations

import json
from unittest import mock

import pytest

from app.agent_runtime.nodes import classify_intent, extract_parameters
from app.config import get_settings
from app.llm import LLMUnavailableError, classify_intent_llm, extract_parameters_llm
from app.services.rag_service import RagService, cosine_similarity


def _mock_ollama_response(content: str) -> mock.MagicMock:
    """构造模拟的 Ollama HTTP 响应."""
    response = mock.MagicMock()
    response.status_code = 200
    response.text = ""
    response.json.return_value = {"message": {"content": content}}
    return response


class TestLLMIntentClassification:
    """LLM 意图识别测试."""

    @mock.patch("httpx.post")
    def test_classify_intent_llm_returns_create_report(self, mock_post: mock.MagicMock) -> None:
        """模拟 Ollama 返回 create_report 意图."""
        mock_post.return_value = _mock_ollama_response(
            json.dumps({"intent": "create_report", "reasoning": "用户要求生成报告"})
        )
        result = classify_intent_llm("生成 2025 年利润表")
        assert result["intent"] == "create_report"
        assert "reasoning" in result

    @mock.patch("httpx.post")
    def test_extract_parameters_llm_returns_year_period_report_type(
        self, mock_post: mock.MagicMock
    ) -> None:
        """模拟 Ollama 返回结构化参数."""
        mock_post.return_value = _mock_ollama_response(
            json.dumps(
                {
                    "title": "2025 年利润表",
                    "report_type": "profit",
                    "year": 2025,
                    "period": "Q2",
                    "document_id": None,
                    "question": "生成 2025 年 Q2 利润表",
                }
            )
        )
        result = extract_parameters_llm("生成 2025 年 Q2 利润表", "create_report")
        assert result["year"] == 2025
        assert result["period"] == "Q2"
        assert result["report_type"] == "profit"

    def test_llm_unavailable_falls_back_to_rule(self) -> None:
        """LLM 不可用时自动降级到规则意图识别."""
        with mock.patch(
            "app.agent_runtime.nodes.classify_intent_llm"
        ) as mock_classify, mock.patch.object(
            get_settings(), "agent_intent_mode", "llm"
        ):
            mock_classify.side_effect = LLMUnavailableError("连接失败")
            state = classify_intent({"question": "2025 年 Q2 净利润是多少"})
            assert state["intent"] == "nl2sql"

    def test_llm_invalid_intent_falls_back_to_rule(self) -> None:
        """LLM 返回无效意图时降级到规则逻辑."""
        with mock.patch(
            "app.agent_runtime.nodes.classify_intent_llm"
        ) as mock_classify, mock.patch.object(
            get_settings(), "agent_intent_mode", "llm"
        ):
            mock_classify.return_value = {"intent": "invalid_intent", "reasoning": "错误"}
            state = classify_intent({"question": "生成 2025 年利润表"})
            assert state["intent"] == "create_report"


class TestLLMParameterExtraction:
    """LLM 参数提取测试."""

    @mock.patch("httpx.post")
    def test_extract_parameters_llm_nl2sql(self, mock_post: mock.MagicMock) -> None:
        """NL2SQL 意图下参数提取保留问题."""
        mock_post.return_value = _mock_ollama_response(
            json.dumps(
                {
                    "title": "2025 年 Q1 营业收入",
                    "report_type": "custom",
                    "year": None,
                    "period": None,
                    "document_id": None,
                    "question": "2025 年 Q1 营业收入是多少",
                }
            )
        )
        result = extract_parameters_llm("2025 年 Q1 营业收入是多少", "nl2sql")
        assert result["question"] == "2025 年 Q1 营业收入是多少"

    def test_extract_parameters_fallback_on_llm_error(self) -> None:
        """参数提取 LLM 失败时降级到规则."""
        with mock.patch(
            "app.agent_runtime.nodes.extract_parameters_llm"
        ) as mock_extract, mock.patch.object(
            get_settings(), "agent_intent_mode", "llm"
        ):
            mock_extract.side_effect = LLMUnavailableError("连接失败")
            state = extract_parameters({"intent": "create_report", "question": "生成 2025 年利润表"})
            assert state["parameters"]["report_type"] == "profit"
            assert state["parameters"]["year"] == 2025


class TestRAGService:
    """RAG 服务测试."""

    def test_chunk_text_splits_paragraphs_and_long_lines(self) -> None:
        """chunk_text 按段落与长度切分文本."""
        from app.services.rag_service import chunk_text

        text = "第一段内容。\n\n第二段内容更长一些。\n" + "x" * 600
        chunks = chunk_text(text, chunk_size=100)
        assert len(chunks) >= 3
        assert all(len(c) <= 100 for c in chunks)

    def test_cosine_similarity(self) -> None:
        """余弦相似度计算正确."""
        a = [1.0, 0.0]
        b = [1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(1.0)

        c = [0.0, 1.0]
        assert cosine_similarity(a, c) == pytest.approx(0.0)

    @mock.patch("app.services.rag_service.embed")
    def test_rag_query_returns_chunks(self, mock_embed: mock.MagicMock) -> None:
        """模拟 embedding 后 RAG 问答返回包含 chunk 的结果."""
        service = RagService()
        # 使用简单二维向量，通过 cosine 相似度区分相关性
        mock_embed.side_effect = lambda text: {
            "公司营收增长": [1.0, 0.0],
            "成本下降": [0.0, 1.0],
            "无关内容": [0.5, 0.5],
            "营收是多少": [0.9, 0.1],
        }.get(text, [0.0, 0.0])

        with mock.patch("app.config.get_settings") as mock_settings:
            settings = mock.MagicMock()
            settings.rag_top_k = 2
            settings.rag_chunk_size = 20
            mock_settings.return_value = settings

            service.index_document(
                "doc-1",
                "公司营收增长\n成本下降\n无关内容",
                tenant_id="tenant-1",
            )
            result = service.query("营收是多少", tenant_id="tenant-1", document_id="doc-1")

        assert any("公司营收增长" in chunk for chunk in result["chunks"])
        assert result["document_id"] == "doc-1"
        assert "answer" in result

    @mock.patch("httpx.post")
    def test_rag_unavailable_raises(self, mock_post: mock.MagicMock) -> None:
        """Ollama embeddings 不可用时抛出 RagUnavailableError."""
        from app.services.rag_service import RagUnavailableError, embed

        mock_post.side_effect = Exception("connection refused")
        with pytest.raises(RagUnavailableError):
            embed("测试文本")
