"""错误自省服务（ReflectionService）单元测试."""

from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import BusinessError, ConfigError, RetryableError, SecurityError
from app.models.error_reflection import ErrorReflection
from app.schemas.common import PaginationParams
from app.services.reflection_service import ReflectionService, create_reflection


def _make_reflection(
    db: Session,
    tenant_id: str | None,
    *,
    category: str = "business",
    resource_type: str | None = None,
    resolved: bool = False,
) -> ErrorReflection:
    """直接构造一条自省日志，绕过服务层以便准备测试数据."""
    reflection = ErrorReflection(
        tenant_id=tenant_id,
        task_name="test-task",
        exception_type="ValueError",
        exception_message="boom",
        error_category=category,
        resource_type=resource_type,
        resolved=resolved,
        resolution="已修复" if resolved else None,
    )
    db.add(reflection)
    db.commit()
    db.refresh(reflection)
    return reflection


def test_reflect_persists_and_classifies_business(db_session: Session) -> None:
    """reflect 应对业务异常正确分类并持久化."""
    service = ReflectionService(db_session)
    reflection = service.reflect(
        BusinessError("参数非法"),
        task_name="report.generate",
        tenant_id="tenant-a",
        resource_type="report",
        resource_id="r-1",
    )

    assert reflection.id is not None
    assert reflection.error_category == "business"
    assert reflection.exception_type == "BusinessError"
    assert reflection.exception_message == "参数非法"
    assert reflection.tenant_id == "tenant-a"
    assert reflection.task_name == "report.generate"
    assert reflection.resource_type == "report"
    assert reflection.resolved is False
    # 业务异常不应记录堆栈
    assert reflection.stack_trace is None
    assert reflection.root_cause is not None
    assert reflection.suggested_fix is not None


def test_reflect_unknown_exception_records_stack_trace(db_session: Session) -> None:
    """未分类异常应记录堆栈以便后续排查."""
    service = ReflectionService(db_session)
    try:
        msg = "未预期错误"
        raise RuntimeError(msg)  # noqa: TRY301 - 仅为构造异常对象
    except RuntimeError as exc:
        reflection = service.reflect(exc)

    assert reflection.error_category == "unknown"
    assert reflection.stack_trace is not None
    assert "RuntimeError" in (reflection.stack_trace or "")
    # 未知异常的根因建议应提示进一步排查
    assert reflection.root_cause is not None
    assert "未分类" in (reflection.root_cause or "")


def test_reflect_category_specific_analyzers(db_session: Session) -> None:
    """retryable/config/security 分类应返回各自的根因与修复建议."""
    service = ReflectionService(db_session)

    cases = [
        (RetryableError("连接超时"), "retryable"),
        (ConfigError("缺少配置"), "config"),
        (SecurityError("越权访问"), "security"),
    ]
    for exc, expected_category in cases:
        reflection = service.reflect(exc)
        assert reflection.error_category == expected_category
        assert reflection.root_cause is not None
        assert reflection.suggested_fix is not None


def test_list_reflections_filters_by_category(db_session: Session) -> None:
    """list_reflections 应按 category 过滤."""
    _make_reflection(db_session, "tenant-a", category="business")
    _make_reflection(db_session, "tenant-a", category="retryable")
    _make_reflection(db_session, "tenant-a", category="retryable")

    service = ReflectionService(db_session)
    items, total = service.list_reflections("tenant-a", category="retryable")

    assert total == 2
    assert len(items) == 2
    assert all(item.error_category == "retryable" for item in items)


def test_list_reflections_pagination(db_session: Session) -> None:
    """list_reflections 应支持分页."""
    for _ in range(5):
        _make_reflection(db_session, "tenant-p", category="business")

    service = ReflectionService(db_session)
    page1, total1 = service.list_reflections(
        "tenant-p", pagination=PaginationParams(page=1, page_size=2)
    )
    page2, total2 = service.list_reflections(
        "tenant-p", pagination=PaginationParams(page=2, page_size=2)
    )

    assert total1 == 5
    assert total2 == 5
    assert len(page1) == 2
    assert len(page2) == 2
    # 两页不应出现重复记录
    assert {item.id for item in page1}.isdisjoint({item.id for item in page2})


def test_get_reflection_tenant_isolation(db_session: Session) -> None:
    """get_reflection 应做租户隔离，跨租户查询返回 None."""
    reflection = _make_reflection(db_session, "tenant-x")
    service = ReflectionService(db_session)

    assert service.get_reflection(reflection.id, tenant_id="tenant-x") is not None
    assert service.get_reflection(reflection.id, tenant_id="tenant-other") is None
    # 未指定租户时也应能查到（便于运维全局排查）
    assert service.get_reflection(reflection.id) is not None


def test_resolve_updates_status_and_resolution(db_session: Session) -> None:
    """resolve 应将日志标记为已解决并保存解决方案."""
    reflection = _make_reflection(db_session, "tenant-r", resolved=False)
    service = ReflectionService(db_session)

    resolved = service.resolve(reflection.id, "重启服务后恢复", tenant_id="tenant-r")

    assert resolved is not None
    assert resolved.resolved is True
    assert resolved.resolution == "重启服务后恢复"


def test_resolve_nonexistent_returns_none(db_session: Session) -> None:
    """resolve 不存在的日志应返回 None 而非抛错."""
    service = ReflectionService(db_session)
    assert service.resolve("nonexistent-id", "x", tenant_id="tenant-r") is None


def test_create_reflection_helper(db_session: Session) -> None:
    """create_reflection 便捷函数应等价于 ReflectionService.reflect."""
    reflection = create_reflection(
        db_session,
        BusinessError("校验失败"),
        task_name="t",
        tenant_id="tenant-h",
    )
    assert reflection.id is not None
    assert reflection.error_category == "business"
    persisted = (
        db_session.query(ErrorReflection)
        .filter(ErrorReflection.id == reflection.id)
        .one_or_none()
    )
    assert persisted is not None
    assert persisted.exception_message == "校验失败"


def test_list_reflections_filters_resolved_and_resource_type(
    db_session: Session,
) -> None:
    """list_reflections 应支持按 resolved / resource_type 过滤."""
    _make_reflection(
        db_session, "tenant-f", category="business", resource_type="report", resolved=False
    )
    _make_reflection(
        db_session,
        "tenant-f",
        category="business",
        resource_type="report",
        resolved=True,
    )
    _make_reflection(
        db_session, "tenant-f", category="business", resource_type="document", resolved=False
    )

    service = ReflectionService(db_session)

    unresolved, total_u = service.list_reflections(
        "tenant-f", resolved=False, resource_type="report"
    )
    assert total_u == 1
    assert unresolved[0].resolved is False
    assert unresolved[0].resource_type == "report"

    resolved_items, total_r = service.list_reflections(
        "tenant-f", resolved=True, resource_type="report"
    )
    assert total_r == 1
    assert resolved_items[0].resolved is True


def test_reflect_preserves_optional_fields(db_session: Session) -> None:
    """reflect 应正确保存 task_id 等可选字段."""
    service = ReflectionService(db_session)
    reflection: Any = service.reflect(
        ConfigError("缺少密钥"),
        task_id="task-123",
        resource_type="secret",
        resource_id="sec-1",
    )
    assert reflection.task_id == "task-123"
    assert reflection.resource_type == "secret"
    assert reflection.resource_id == "sec-1"
    assert reflection.error_category == "config"
