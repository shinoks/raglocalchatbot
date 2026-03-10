from uuid import UUID

from app.db.session import SessionLocal
from app.services.ingestion import IngestionService


def process_document_job(document_id: str, job_id: str) -> None:
    with SessionLocal() as session:
        IngestionService().process(session, UUID(document_id), UUID(job_id))
