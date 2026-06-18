"""文档解析异步任务测试."""

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.user import User
from app.parser.simple_parser import SimpleDocumentParser
from app.security import get_password_hash
from app.tasks.document_tasks import parse_document_task


def _create_document(db: Session, tenant: Tenant, user: User, filename: str) -> Document:
    """辅助函数：创建并提交测试文档."""
    doc = Document(
        tenant_id=tenant.id,
        created_by=user.id,
        filename=filename,
        storage_key=f"docs/{filename}",
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def test_parse_document_task_success() -> None:
    """测试文档解析任务成功更新状态与结果.

    注意：Celery 任务使用独立的 SessionLocal，为避免 SQLite 事务隔离导致任务看不到
    未提交数据，本测试在独立会话中创建租户、用户与文档并真实提交。
    """
    db = SessionLocal()
    try:
        tenant = Tenant(name="Task Test Tenant", code="task-test")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        user = User(
            tenant_id=tenant.id,
            username="tasktester",
            email="task@example.com",
            hashed_password=get_password_hash("testpass"),
            role="admin",
            is_active="Y",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        doc = _create_document(db, tenant, user, "profit_q2_2025.pdf")

        result = parse_document_task.delay(doc.id).get()

        assert result["status"] == "success"
        assert result["document_id"] == doc.id

        db.refresh(doc)
        assert doc.status == "success"
        assert doc.confidence == 0.6
        assert doc.parse_result is not None
        assert doc.parse_result["detected_year"] == 2025
        assert doc.parse_result["detected_period"] == "Q2"
        assert doc.error_message is None
    finally:
        db.close()


def test_parse_document_task_not_found() -> None:
    """测试对不存在文档执行任务返回失败但不重试."""
    result = parse_document_task.delay("non-existent-id").get()

    assert result["status"] == "failed"
    assert result["retry"] is False


def test_simple_parser_extracts_metadata() -> None:
    """测试简单解析器从文件名提取元数据."""
    doc = Document(
        tenant_id="t1",
        created_by="u1",
        filename="balance_2024_h1.xlsx",
        storage_key="docs/balance_2024_h1.xlsx",
        status="pending",
    )
    parser = SimpleDocumentParser(doc)

    result = parser.parse()

    assert result["extension"] == "xlsx"
    assert result["detected_year"] == 2024
    assert result["detected_period"] == "H1"
    assert parser.confidence() == 0.6
