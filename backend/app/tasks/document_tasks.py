"""文档解析异步任务."""

from typing import Any

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.document import Document
from app.parser.csv_financial_parser import CsvFinancialParser
from app.parser.simple_parser import SimpleDocumentParser
from app.services.audit_service import log_action
from app.services.financial_import_service import import_financial_records
from app.storage import get_storage_client


def _get_document(db: Session, document_id: str) -> Document | None:
    """按 ID 获取文档."""
    return db.query(Document).filter(Document.id == document_id).first()


def _update_document_status(
    db: Session,
    document: Document,
    status: str,
    parse_result: dict[str, Any] | None = None,
    confidence: float | None = None,
    error_message: str | None = None,
) -> None:
    """更新文档解析状态与结果."""
    document.status = status
    if parse_result is not None:
        document.parse_result = parse_result
    if confidence is not None:
        document.confidence = confidence
    if error_message is not None:
        document.error_message = error_message
    db.commit()


def _file_extension(filename: str) -> str:
    """获取文件扩展名."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)  # type: ignore[untyped-decorator]
def parse_document_task(self: Any, document_id: str) -> dict[str, Any]:
    """异步解析文档任务.

    Args:
        document_id: 待解析文档 ID

    Returns:
        解析结果摘要
    """
    db = SessionLocal()
    try:
        document = _get_document(db, document_id)
        if document is None:
            return {"status": "failed", "error": f"Document {document_id} not found", "retry": False}

        _update_document_status(db, document, "processing")

        ext = _file_extension(document.filename)

        if ext == "csv":
            parse_result, confidence = _parse_csv_document(db, document)
        else:
            parser = SimpleDocumentParser(document)
            parse_result = parser.parse()
            confidence = parser.confidence()

        _update_document_status(
            db,
            document,
            "success",
            parse_result=parse_result,
            confidence=confidence,
        )

        log_action(
            db=db,
            action="document.parse.success",
            resource=f"document://{document_id}",
        )

        return {
            "document_id": document_id,
            "status": "success",
            "confidence": confidence,
        }
    except ValueError as exc:
        # 业务错误不重试
        document = _get_document(db, document_id)
        if document is not None:
            _update_document_status(
                db,
                document,
                "failed",
                error_message=str(exc),
            )
            log_action(
                db=db,
                action="document.parse.failed",
                resource=f"document://{document_id}",
                result="failed",
                reason=str(exc),
            )
        return {
            "document_id": document_id,
            "status": "failed",
            "error": str(exc),
            "retry": False,
        }
    except Exception as exc:
        document = _get_document(db, document_id)
        if document is not None:
            _update_document_status(
                db,
                document,
                "failed",
                error_message=str(exc),
            )
            log_action(
                db=db,
                action="document.parse.failed",
                resource=f"document://{document_id}",
                result="failed",
                reason=str(exc),
            )
        # 可重试异常则自动重试
        raise self.retry(exc=exc) from exc
    finally:
        db.close()


def _parse_csv_document(
    db: Session,
    document: Document,
) -> tuple[dict[str, Any], float]:
    """解析 CSV 财务文件并导入数据库.

    Returns:
        (parse_result, confidence)
    """
    storage = get_storage_client()
    content = storage.download_bytes(document.storage_key)

    parser = CsvFinancialParser(content)
    records = parser.parse()

    simple = SimpleDocumentParser(document)
    default_year = simple._extract_year(document.filename)
    default_period = simple._extract_period(document.filename) or "annual"

    imported = import_financial_records(
        db=db,
        tenant_id=document.tenant_id,
        records=records,
        default_year=default_year,
        default_period=default_period,
    )

    parse_result = {
        "format": "csv",
        "imported_count": len(imported),
        "records": records,
        "detected_year": default_year,
        "detected_period": default_period,
    }
    return parse_result, parser.confidence()
