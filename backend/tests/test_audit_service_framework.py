"""audit_service 独立审计框架测试."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User
from audit_service import (
    AuditEvent,
    AuditLogger,
    CallbackAuditSink,
    DatabaseAuditSink,
    LoggingAuditSink,
    get_default_logger,
    log_action,
)


@pytest.fixture(autouse=True)
def _isolate_default_logger() -> Generator[None, None, None]:
    """每个测试前后清空默认 logger，避免 sink 跨测试污染."""
    logger = get_default_logger()
    logger.clear_sinks()
    yield
    logger.clear_sinks()


def test_audit_event_defaults() -> None:
    event = AuditEvent(action="create", resource="report:1")
    assert event.result == "success"
    assert event.tenant_id is None
    assert event.user_id is None
    assert event.metadata == {}


def test_audit_event_from_user(test_user: User) -> None:
    event = AuditEvent.from_user(test_user, "update", "report:2", result="failed")
    assert event.tenant_id == test_user.tenant_id
    assert event.user_id == test_user.id
    assert event.result == "failed"


def test_to_audit_log_kwargs_round_trip() -> None:
    event = AuditEvent(
        action="export",
        resource="report:3",
        result="success",
        tenant_id="t1",
        user_id="u1",
        input_hash="ih",
        output_hash="oh",
        model_version="v1",
        ip="10.0.0.1",
        reason="ok",
    )
    kwargs = event.to_audit_log_kwargs()
    assert kwargs == {
        "tenant_id": "t1",
        "user_id": "u1",
        "action": "export",
        "resource": "report:3",
        "input_hash": "ih",
        "output_hash": "oh",
        "model_version": "v1",
        "ip": "10.0.0.1",
        "result": "success",
        "reason": "ok",
    }


def test_database_sink_write_adds_audit_log(db_session: Session, test_user: User) -> None:
    sink = DatabaseAuditSink(db_session)
    assert sink.is_available() is True

    event = AuditEvent.from_user(test_user, "delete", "document:9")
    sink.write(event)
    db_session.flush()

    logs = db_session.query(AuditLog).filter(AuditLog.action == "delete").all()
    assert len(logs) == 1
    assert logs[0].action == "delete"
    assert logs[0].user_id == test_user.id
    assert logs[0].resource == "document:9"


def test_database_sink_without_session_is_unavailable() -> None:
    sink = DatabaseAuditSink(None)
    assert sink.is_available() is False
    # 不应抛异常
    sink.write(AuditEvent(action="x", resource="y"))


def test_database_sink_bind_creates_new_instance(db_session: Session) -> None:
    sink = DatabaseAuditSink(None)
    assert sink.is_available() is False
    bound = sink.bind(db_session)
    assert bound is not sink
    assert bound.is_available() is True


def test_logging_sink_write_does_not_raise() -> None:
    sink = LoggingAuditSink()
    assert sink.is_available() is True
    sink.write(AuditEvent(action="login", resource="user:1"))


def test_callback_sink_invokes_callback() -> None:
    received: list[AuditEvent] = []
    sink = CallbackAuditSink(received.append, sink_name="spy")
    assert sink.name == "spy"
    assert sink.is_available() is True

    event = AuditEvent(action="read", resource="report:4")
    sink.write(event)
    assert received == [event]

    sink.disable()
    assert sink.is_available() is False


def test_logger_add_and_remove_sink() -> None:
    logger = AuditLogger()
    sink = LoggingAuditSink()
    assert logger.add_sink(sink) is logger
    assert len(logger.sinks) == 1
    assert logger.remove_sink("logging") is True
    assert logger.sinks == []
    assert logger.remove_sink("missing") is False


def test_logger_clear_sinks() -> None:
    logger = AuditLogger([LoggingAuditSink(), CallbackAuditSink(lambda _e: None)])
    assert len(logger.sinks) == 2
    logger.clear_sinks()
    assert logger.sinks == []


def test_logger_dispatches_to_all_sinks() -> None:
    received_a: list[AuditEvent] = []
    received_b: list[AuditEvent] = []
    logger = AuditLogger(
        [CallbackAuditSink(received_a.append, sink_name="a"), CallbackAuditSink(received_b.append, sink_name="b")]
    )
    event = AuditEvent(action="create", resource="report:5")
    logger.log(event)
    assert received_a == [event]
    assert received_b == [event]


def test_logger_skips_unavailable_sinks() -> None:
    received: list[AuditEvent] = []
    sink = CallbackAuditSink(received.append)
    sink.disable()
    logger = AuditLogger([sink])
    logger.log(AuditEvent(action="x", resource="y"))
    assert received == []


def test_logger_sink_failure_does_not_break_others() -> None:
    received: list[AuditEvent] = []

    def boom(_event: AuditEvent) -> None:
        raise RuntimeError("sink exploded")

    logger = AuditLogger(
        [CallbackAuditSink(boom, sink_name="boom"), CallbackAuditSink(received.append, sink_name="ok")]
    )
    logger.log(AuditEvent(action="x", resource="y"))
    # 失败的 sink 不影响后续 sink
    assert len(received) == 1


def test_get_default_logger_is_singleton() -> None:
    a = get_default_logger()
    b = get_default_logger()
    assert a is b


def test_log_action_writes_db_and_returns_log(
    db_session: Session, test_user: User
) -> None:
    log = log_action(
        db_session,
        action="report.create",
        resource="report:100",
        user=test_user,
        commit=False,
    )
    assert log.action == "report.create"
    assert log.user_id == test_user.id
    # commit=False 不提交，显式 flush 后分配主键
    db_session.flush()
    assert log.id is not None


def test_log_action_dispatches_to_registered_sink(
    db_session: Session, test_user: User
) -> None:
    received: list[AuditEvent] = []
    get_default_logger().add_sink(CallbackAuditSink(received.append))

    log_action(
        db_session,
        action="report.export",
        resource="report:200",
        user=test_user,
        commit=False,
    )

    assert len(received) == 1
    assert received[0].action == "report.export"
    assert received[0].user_id == test_user.id


def test_app_services_audit_service_delegates() -> None:
    """app.services.audit_service.log_action 应与 audit_service.log_action 是同一函数."""
    from app.services import audit_service as legacy

    assert legacy.log_action is log_action
