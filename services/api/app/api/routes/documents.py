from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import AdminUser, Document, DocumentChunk, IngestionJob, JobType
from app.schemas.api import CitationResponse, DocumentResponse, IngestionJobResponse
from app.services.storage import StorageService
from app.workers.queue import get_ingestion_queue

router = APIRouter(prefix="/api/admin", tags=["documents"])
settings = get_settings()


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    _: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    documents = db.scalars(select(Document).order_by(Document.uploaded_at.desc())).all()
    return list(documents)


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    _: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    storage = StorageService(settings.upload_dir)
    stored = await storage.save_upload(file, settings.max_upload_bytes)

    existing = db.scalar(select(Document).where(Document.checksum == stored.checksum))
    if existing is not None:
        try:
            storage.delete(stored.path)
        except FileNotFoundError:
            pass
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document already exists.")

    document = Document(
        filename=stored.original_filename,
        checksum=stored.checksum,
        format=stored.format,
        storage_path=str(stored.path),
        status="processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    job = IngestionJob(document_id=document.id, job_type=JobType.ingest.value, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        queue_job = get_ingestion_queue().enqueue(
            "app.workers.tasks.process_document_job",
            str(document.id),
            str(job.id),
            job_timeout="45m",
            result_ttl=600,
        )
        job.queue_job_id = queue_job.id
        db.add(job)
        db.commit()
    except Exception as exc:
        job.status = "failed"
        job.error_message = f"Queue enqueue failed: {exc}"
        document.status = "failed"
        document.error_message = job.error_message
        db.add_all([job, document])
        db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue is unavailable.") from exc

    return document


@router.post("/documents/{document_id}/reindex", response_model=IngestionJobResponse, status_code=status.HTTP_202_ACCEPTED)
def reindex_document(
    document_id: str,
    _: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IngestionJobResponse:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    document.status = "processing"
    document.error_message = None
    job = IngestionJob(document_id=document.id, job_type=JobType.reindex.value, status="queued")
    db.add_all([document, job])
    db.commit()
    db.refresh(job)

    try:
        queue_job = get_ingestion_queue().enqueue(
            "app.workers.tasks.process_document_job",
            str(document.id),
            str(job.id),
            job_timeout="45m",
            result_ttl=600,
        )
    except Exception as exc:
        job.status = "failed"
        job.error_message = f"Queue enqueue failed: {exc}"
        document.status = "failed"
        document.error_message = job.error_message
        db.add_all([job, document])
        db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue is unavailable.") from exc

    job.queue_job_id = queue_job.id
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    _: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    storage_path = document.storage_path
    db.delete(document)
    db.commit()

    try:
        StorageService(settings.upload_dir).delete(storage_path)
    except FileNotFoundError:
        pass


@router.get("/documents/{document_id}/citations", response_model=list[CitationResponse])
def get_document_citations(
    document_id: str,
    _: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[CitationResponse]:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    chunks = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index.asc())
        .limit(20)
    ).all()
    return [
        CitationResponse(
            document_id=document.id,
            filename=document.filename,
            page=chunk.page_number,
            section=chunk.section_title,
            excerpt=chunk.citation_excerpt,
        )
        for chunk in chunks
    ]


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
def get_job(
    job_id: str,
    _: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IngestionJobResponse:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job
