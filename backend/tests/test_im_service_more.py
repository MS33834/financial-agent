"""IM 服务（app.services.im_service）补全测试.

覆盖：
- _format_service_error: 各种业务异常的友好化
- _resolve_report_id_from_command: 数字序号 / report_id / 错误情况
- IMServiceError 简单实例化
"""


from app.im.commands import BotCommand
from app.services.im_service import (
    IMServiceError,
    _format_service_error,
    _resolve_report_id_from_command,
)

# ------------------------------------------------------------------
# _format_service_error
# ------------------------------------------------------------------


def test_format_error_permission() -> None:
    """权限类异常应返回权限不足提示."""
    assert "权限不足" in _format_service_error(Exception("无权操作"))


def test_format_error_not_found() -> None:
    """资源不存在异常应返回未找到提示."""
    assert "未找到" in _format_service_error(Exception("资源不存在"))


def test_format_error_wrong_status() -> None:
    """报告状态错误应返回状态提示."""
    msg = _format_service_error(Exception("该报告不处于待审核状态"))
    assert "待审核状态" in msg


def test_format_error_invalid_action() -> None:
    """无效审批动作应返回支持的列表."""
    msg = _format_service_error(Exception("无效的审核动作"))
    assert "approve" in msg and "reject" in msg and "modify" in msg


def test_format_error_safety_check_passthrough() -> None:
    """安全校验异常应原样透传前缀."""
    msg = _format_service_error(Exception("安全校验：检测到 prompt injection"))
    assert "安全校验" in msg


def test_format_error_generic_fallback() -> None:
    """未识别异常应使用通用兜底文案."""
    msg = _format_service_error(Exception("some random network error"))
    assert "服务处理异常" in msg


# ------------------------------------------------------------------
# _resolve_report_id_from_command
# ------------------------------------------------------------------


def test_resolve_report_id_from_kwargs() -> None:
    """kwargs 中 report_id 优先."""
    cmd = BotCommand(name="/approve", args=[], kwargs={"report_id": "r-001"})
    rid, err = _resolve_report_id_from_command(cmd, user_id="u1")
    assert rid == "r-001"
    assert err is None


def test_resolve_report_id_from_first_arg() -> None:
    """args[0] 在 kwargs 缺失时使用."""
    cmd = BotCommand(name="/approve", args=["r-002"], kwargs={})
    rid, err = _resolve_report_id_from_command(cmd, user_id="u1")
    assert rid == "r-002"
    assert err is None


def test_resolve_report_id_empty_returns_error() -> None:
    """既无 kwargs 也无 args 应返回错误提示."""
    cmd = BotCommand(name="/approve", args=[], kwargs={})
    rid, err = _resolve_report_id_from_command(cmd, user_id="u1")
    assert rid is None
    assert "请输入 report_id" in (err or "")


def test_resolve_report_id_digit_resolves_to_cached() -> None:
    """数字序号应解析为 /pending 缓存中的 report_id."""
    import app.services.im_service as im_service

    im_service._pending_reports["u1"] = ["r-A", "r-B", "r-C"]
    cmd = BotCommand(name="/approve", args=["2"], kwargs={})
    rid, err = _resolve_report_id_from_command(cmd, user_id="u1")
    assert rid == "r-B"
    assert err is None
    # 清理
    im_service._pending_reports.pop("u1", None)


def test_resolve_report_id_digit_no_cache_returns_error() -> None:
    """数字序号但无缓存时应返回错误."""
    import app.services.im_service as im_service

    im_service._pending_reports.pop("u1", None)
    cmd = BotCommand(name="/approve", args=["1"], kwargs={})
    rid, err = _resolve_report_id_from_command(cmd, user_id="u1")
    assert rid is None
    assert "未找到待审报告缓存" in (err or "")


def test_resolve_report_id_digit_out_of_range() -> None:
    """序号越界应返回错误."""
    import app.services.im_service as im_service

    im_service._pending_reports["u1"] = ["r-A"]
    cmd = BotCommand(name="/approve", args=["5"], kwargs={})
    rid, err = _resolve_report_id_from_command(cmd, user_id="u1")
    assert rid is None
    assert "超出范围" in (err or "")
    im_service._pending_reports.pop("u1", None)


# ------------------------------------------------------------------
# IMServiceError
# ------------------------------------------------------------------


def test_im_service_error_instantiation() -> None:
    """IMServiceError 应可被实例化并保留消息."""
    exc = IMServiceError("boom")
    assert str(exc) == "boom"
    assert isinstance(exc, Exception)
