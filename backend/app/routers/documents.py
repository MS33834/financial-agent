"""文档解析任务路由."""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.database import get_db
from app.dependencies import get_current_active_user, get_pagination, require_role
from app.models.user import User
from app.schemas.common import DataResponse, PaginatedResponse, PaginationParams
from app.schemas.document import DocumentCreate, DocumentResponse
from app.services.document_service import create_document_task, get_document, list_documents
from app.storage import get_storage_client

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


def _to_document_response(doc: Any) -> dict[str, Any]:
    """将 ORM 对象转为响应字典."""
    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "confidence": doc.confidence,
        "parse_result": doc.parse_result,
        "error_message": doc.error_message,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("", response_model=DataResponse[DocumentResponse], status_code=status.HTTP_201_CREATED)
def create_document(
    data: DocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.FINANCE_MANAGER)),
) -> dict[str, Any]:
    """创建文档解析任务."""
    doc = create_document_task(db=db, data=data, user=user)
    return {"code": 0, "message": "ok", "data": _to_document_response(doc)}


@router.post(
    "/upload", response_model=DataResponse[DocumentResponse], status_code=status.HTTP_201_CREATED
)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.FINANCE_MANAGER)),
) -> dict[str, Any]:
    """上传文件并创建文档解析任务."""
    content = await file.read()
    filename = file.filename or "unknown"

    storage = get_storage_client()
    key = f"documents/{user.tenant_id}/{uuid4()}/{filename}"
    storage.upload_bytes(
        key=key,
        data=content,
        content_type=file.content_type or "application/octet-stream",
    )

    doc = create_document_task(
        db=db,
        data=DocumentCreate(filename=filename, storage_key=key),
        user=user,
    )
    return {"code": 0, "message": "ok", "data": _to_document_response(doc)}


@router.get("", response_model=PaginatedResponse[DocumentResponse])
def list_documents_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
    pagination: PaginationParams = Depends(get_pagination),
) -> dict[str, Any]:
    """查询文档解析任务列表."""
    items, total = list_documents(
        db=db,
        tenant_id=user.tenant_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "total": total,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "items": [_to_document_response(doc) for doc in items],
        },
    }


@router.get("/{document_id}", response_model=DataResponse[DocumentResponse])
def get_document_api(
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """获取单个文档解析任务."""
    doc = get_document(db=db, document_id=document_id, tenant_id=user.tenant_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return {"code": 0, "message": "ok", "data": _to_document_response(doc)}
