"""Mineru PDF 解析客户端测试."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.config import get_settings
from app.parser.mineru_client import MineruClient, MineruError, MineruNotConfigured
from app.parser.pdf_parser import PdfParser


def test_mineru_client_returns_records() -> None:
    """MineruClient 应正确解析返回的 JSON 并扁平化表格."""
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "tables": [
            [
                {"科目": "营业收入", "金额": "1000"},
                {"科目": "净利润", "金额": "200"},
            ]
        ],
        "text": "营业收入 1000，净利润 200",
        "confidence": 0.92,
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.post", return_value=fake_response) as mock_post:
        client = MineruClient(api_url="http://localhost:8000")
        result = client.parse(b"fake-pdf", "profit_2025_q2.pdf")

    mock_post.assert_called_once()
    assert result["format"] == "mineru"
    assert result["filename"] == "profit_2025_q2.pdf"
    assert result["extension"] == "pdf"
    assert result["detected_year"] == 2025
    assert result["detected_period"] == "Q2"
    assert result["records"] == [
        {"科目": "营业收入", "金额": "1000"},
        {"科目": "净利润", "金额": "200"},
    ]
    assert result["text"] == "营业收入 1000，净利润 200"
    assert result["confidence"] == 0.92


def test_mineru_client_not_configured() -> None:
    """未配置 api_url 时应抛出 MineruNotConfigured."""
    client = MineruClient(api_url=None)
    with pytest.raises(MineruNotConfigured):
        client.parse(b"fake-pdf", "file.pdf")


def test_mineru_client_request_error() -> None:
    """HTTP 请求失败时应抛出 MineruError."""
    with patch("httpx.post", side_effect=httpx.ConnectError("connection refused")):
        client = MineruClient(api_url="http://localhost:8000")
        with pytest.raises(MineruError, match="Mineru 请求失败"):
            client.parse(b"fake-pdf", "file.pdf")


def test_pdf_parser_falls_back_when_mineru_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mineru 失败后 PdfParser 应降级到 pdfplumber 并返回结果."""
    settings = get_settings()
    monkeypatch.setattr(settings, "mineru_api_url", "http://mineru:8000")

    with patch(
        "httpx.post",
        side_effect=httpx.ConnectError("mineru unavailable"),
    ):
        fake_pdf = MagicMock()
        fake_pdf.pages = [
            MagicMock(
                extract_text=lambda: "营业收入 1000",
                extract_tables=lambda: [[["科目", "金额"], ["营业收入", "1000"]]],
            )
        ]
        fake_context = MagicMock()
        fake_context.__enter__ = lambda _self: fake_pdf
        fake_context.__exit__ = lambda _self, _exc_type, _exc_val, _exc_tb: None

        monkeypatch.setattr("pdfplumber.open", lambda _data: fake_context)

        parser = PdfParser()
        result = parser.parse(b"fake-pdf", "profit_2025_q2.pdf")

    assert result["format"] == "pdf"
    assert result["filename"] == "profit_2025_q2.pdf"
    assert result["detected_year"] == 2025
    assert result["detected_period"] == "Q2"
    assert result["text"] == "营业收入 1000"
    assert result["confidence"] == 0.85
    assert result["records"] == [{"科目": "营业收入", "金额": "1000"}]
