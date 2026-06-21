"""文档解析异步任务."""

from typing import Any

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.document import Document
from app.models.user import User
from app.parser import ExcelParser, PdfParser, cleaner  # noqa: F401
from app.parser.base import ParserRegistry
from app.parser.csv_financial_parser import CsvFinancialParser
from app.parser.simple_parser import SimpleDocumentParser
from app.parser.utils import extract_period, extract_year
from app.services.audit_service import log_action
from app.services.financial_import_service import import_financial_records
from app.storage import get_storage_client
from app.tasks.utils import is_retryable_error


def _get_document(db: Session, document_id: str) -> Document | None:
    return db.query(Document).filter(Document.id == document_id).first()


def _get_document_user(db: Session, document: Document | None) -> User | None:
    if document is None or not document.created_by:
        return None
    return db.query(User).filter(User.id == document.created_by).first()


def _update_document_status(
    db: Session,
    document: Document,
    status: str,
    parse_result: dict[str, Any] | None = None,
    confidence: float | None = None,
    error_message: str | None = None,
) -> None:
    document.status = status
    if parse_result is not None:
        document.parse_result = parse_result
    if confidence is not None:
        document.confidence = confidence
    if error_message is not None:
        document.error_message = error_message
    db.commit()


def _file_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)  # type: ignore[untyped-decorator]
def parse_document_task(self: Any, document_id: str) -> dict[str, Any]:
    """异步解析文档任务。"""
    db = SessionLocal()
    try:
        document = _get_document(db, document_id)
        if document is None:
            return {
                "status": "failed",
                "error": f"Document {document_id} not found",
                "retry": False,
            }

        _update_document_status(db, document, "processing")

        ext = _file_extension(document.filename)
        storage = get_storage_client()
        content = storage.download_bytes(document.storage_key)

        if ext == "csv":
            parse_result, records = _parse_csv_document(document, content)
            confidence = parse_result.get("confidence", 0.95)
        else:
            parser = ParserRegistry.get_parser(ext) or SimpleDocumentParser()
            parse_result = parser.parse(content, document.filename)
            records = parse_result.get("records", [])
            confidence = parse_result.get("confidence", 0.3)

        # 清洗记录并计算最终置信度
        original_count = len(records)
        cleaned_records = cleaner.clean_records(records)
        cleaned_count = len(cleaned_records)
        parse_result["records"] = cleaned_records
        parse_result["original_count"] = original_count
        parse_result["cleaned_count"] = cleaned_count
        confidence = cleaner.calculate_confidence(original_count, cleaned_count, confidence)

        # 将结构化记录导入财务数据表
        if cleaned_records:
            default_year = parse_result.get("detected_year") or extract_year(document.filename)
            default_period = parse_result.get("detected_period") or extract_period(
                document.filename
            )
            imported = import_financial_records(
                db=db,
                tenant_id=document.tenant_id,
                records=cleaned_records,
                default_year=default_year,
                default_period=default_period or "annual",
            )
            parse_result["imported_count"] = len(imported)

        final_status = "success" if confidence >= 0.7 and cleaned_count > 0 else "needs_review"
        _update_document_status(
            db,
            document,
            final_status,
            parse_result=parse_result,
            confidence=confidence,
        )

        user = _get_document_user(db, document)
        log_action(
            db=db,
            action=f"document.parse.{final_status}",
            resource=f"document://{document_id}",
            user=user,
        )

        return {
            "document_id": document_id,
            "status": final_status,
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
            user = _get_document_user(db, document)
            log_action(
                db=db,
                action="document.parse.failed",
                resource=f"document://{document_id}",
                result="failed",
                reason=str(exc),
                user=user,
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
            user = _get_document_user(db, document)
            log_action(
                db=db,
                action="document.parse.failed",
                resource=f"document://{document_id}",
                result="failed",
                reason=str(exc),
                user=user,
            )
        if is_retryable_error(exc):
            raise self.retry(exc=exc) from exc
        return {
            "document_id": document_id,
            "status": "failed",
            "error": str(exc),
            "retry": False,
        }
    finally:
        db.close()


def _parse_csv_document(
    document: Document,
    content: bytes,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    parser = CsvFinancialParser(content)
    records = parser.parse()

    parse_result = {
        "format": "csv",
        "records": records,
        "detected_year": extract_year(document.filename),
        "detected_period": extract_period(document.filename),
        "confidence": parser.confidence(),
    }
    return parse_result, records
