"""文档解析任务服务."""

from contextlib import suppress

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentCreate
from app.services.audit_service import log_action
from app.tasks.document_tasks import parse_document_task


def create_document_task(
    db: Session,
    data: DocumentCreate,
    user: User,
) -> Document:
    """创建文档解析任务并触发异步解析."""
    doc = Document(
        tenant_id=user.tenant_id,
        created_by=user.id,
        filename=data.filename,
        storage_key=data.storage_key,
        status="pending",
    )
    db.add(doc)
    db.flush()  # 获取 ID 但不提交

    log_action(
        db=db,
        action="document.create",
        resource=f"document://{doc.id}",
        user=user,
        commit=False,
    )
    db.commit()
    db.refresh(doc)

    # 触发异步解析；测试环境 eager 模式下同步执行
    parse_document_task.delay(doc.id)

    with suppress(Exception):
        from app.metrics import FA_BUSINESS_OPERATIONS_TOTAL

        FA_BUSINESS_OPERATIONS_TOTAL.labels(operation="document_created").inc()

    return doc


def get_document(db: Session, document_id: str, tenant_id: str) -> Document | None:
    """按 ID 和租户获取文档."""
    return (
        db.query(Document)
        .filter(Document.id == document_id, Document.tenant_id == tenant_id)
        .first()
    )


def list_documents(
    db: Session,
    tenant_id: str,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
) -> tuple[list[Document], int]:
    """分页查询文档列表."""
    query = db.query(Document).filter(Document.tenant_id == tenant_id)
    if status:
        query = query.filter(Document.status == status)
    total = query.count()
    items = (
        query.order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total
