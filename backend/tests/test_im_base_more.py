"""IM 机器人基类与注册表（app.im.base）补全测试."""

import urllib.error
from typing import Any
from unittest.mock import MagicMock, patch

from app.im.base import (
    BaseIMBot,
    IMBotRegistry,
    IMMessage,
    send_webhook_with_retry,
)


def test_im_message_defaults() -> None:
    """IMMessage 所有字段都应有默认值."""
    msg = IMMessage()
    assert msg.user_id == ""
    assert msg.username == ""
    assert msg.tenant_id == ""
    assert msg.text == ""
    assert msg.raw_payload is None


def test_im_message_roundtrip() -> None:
    """IMMessage 应能序列化为 dict."""
    msg = IMMessage(user_id="u1", username="alice", text="hello", raw_payload={"k": "v"})
    dumped = msg.model_dump()
    assert dumped["user_id"] == "u1"
    assert dumped["text"] == "hello"
    assert dumped["raw_payload"] == {"k": "v"}


def test_send_webhook_success() -> None:
    """成功响应 200 时返回 True."""
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)
    with patch("app.im.base.urllib.request.urlopen", return_value=fake_resp):
        result = send_webhook_with_retry("http://x", b"{}")
    assert result is True


def test_send_webhook_non_200_returns_false() -> None:
    """非 200 响应不应触发重试，直接返回 False."""
    fake_resp = MagicMock()
    fake_resp.status = 500
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)
    with patch("app.im.base.urllib.request.urlopen", return_value=fake_resp) as mock_open:
        result = send_webhook_with_retry("http://x", b"{}", max_retries=3)
    assert result is False
    # 500 不重试，只调用 1 次
    assert mock_open.call_count == 1


def test_send_webhook_retries_on_urlerror() -> None:
    """URLError 应触发重试."""
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)

    call_count = {"n": 0}

    def _urlopen(*_args: object, **_kwargs: object) -> MagicMock:
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise urllib.error.URLError("conn refused")
        return fake_resp

    with patch("app.im.base.urllib.request.urlopen", side_effect=_urlopen), \
         patch("app.im.base.time.sleep") as mock_sleep:
        result = send_webhook_with_retry("http://x", b"{}", max_retries=2)
    assert result is True
    assert call_count["n"] == 2
    # 第一次失败后 sleep 一次
    assert mock_sleep.call_count == 1


def test_send_webhook_gives_up_after_max_retries() -> None:
    """重试耗尽后返回 False."""
    with patch("app.im.base.urllib.request.urlopen", side_effect=OSError("down")), \
         patch("app.im.base.time.sleep"):
        result = send_webhook_with_retry("http://x", b"{}", max_retries=1)
    assert result is False


def test_im_bot_registry_register_and_get() -> None:
    """register / get_bot / list_platforms 应协同工作."""

    @IMBotRegistry.register("test-platform-xyz")
    class _Bot(BaseIMBot):
        def verify_signature(self, payload: dict[str, Any], headers: dict[str, str], raw_body: bytes | None = None) -> bool:  # noqa: ARG002
            return True

        def parse_message(self, payload: dict[str, Any]) -> IMMessage:  # noqa: ARG002
            return IMMessage()

        def build_response(self, content: str, msg_type: str = "text") -> dict[str, Any]:  # noqa: ARG002
            return {}

    # platform_name 应被设置为 "test-platform-xyz"
    assert _Bot.platform_name == "test-platform-xyz"
    # 通过平台名能拿到实例
    bot = IMBotRegistry.get_bot("test-platform-xyz")
    assert isinstance(bot, _Bot)
    # 列表应包含该平台
    assert "test-platform-xyz" in IMBotRegistry.list_platforms()


def test_im_bot_registry_get_unknown_returns_none() -> None:
    """未注册的平台应返回 None."""
    assert IMBotRegistry.get_bot("not-registered-platform-zzz") is None


def test_base_im_bot_build_error_response() -> None:
    """build_error_response 应返回包含错误文本的响应."""

    class _Stub(BaseIMBot):
        def verify_signature(self, payload: dict[str, Any], headers: dict[str, str], raw_body: bytes | None = None) -> bool:  # noqa: ARG002
            return True

        def parse_message(self, payload: dict[str, Any]) -> IMMessage:  # noqa: ARG002
            return IMMessage()

        def build_response(self, content: str, msg_type: str = "text") -> dict[str, Any]:  # noqa: ARG002
            return {"content": content}

    stub = _Stub()
    resp = stub.build_error_response("something failed")
    assert "something failed" in resp["content"]
    assert "请求处理失败" in resp["content"]


def test_base_im_bot_default_send_message_returns_false() -> None:
    """BaseIMBot.send_message 默认实现应返回 False."""

    class _Stub(BaseIMBot):
        def verify_signature(self, payload: dict[str, Any], headers: dict[str, str], raw_body: bytes | None = None) -> bool:  # noqa: ARG002
            return True

        def parse_message(self, payload: dict[str, Any]) -> IMMessage:  # noqa: ARG002
            return IMMessage()

        def build_response(self, content: str, msg_type: str = "text") -> dict[str, Any]:  # noqa: ARG002
            return {}

    assert _Stub().send_message("hi") is False
