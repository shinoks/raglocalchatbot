from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from docx import Document as DocxDocument
from pypdf import PdfReader
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Document, DocumentChunk, DocumentStatus, IngestionJob, JobStatus
from app.services.ollama import OllamaService

settings = get_settings()


class IngestionError(RuntimeError):
    pass


class ScannedDocumentError(IngestionError):
    pass


@dataclass(slots=True)
class ExtractedSegment:
    text: str
    page_number: int | None = None
    section_title: str | None = None


@dataclass(slots=True)
class ChunkPayload:
    content: str
    excerpt: str
    page_number: int | None
    section_title: str | None


def utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def chunk_segments(
    segments: list[ExtractedSegment],
    chunk_size_words: int = settings.chunk_size_words,
    overlap_words: int = settings.chunk_overlap_words,
) -> list[ChunkPayload]:
    payloads: list[ChunkPayload] = []
    step = max(1, chunk_size_words - overlap_words)

    for segment in segments:
        words = segment.text.split()
        start = 0
        while start < len(words):
            chunk_words = words[start : start + chunk_size_words]
            if not chunk_words:
                break
            content = " ".join(chunk_words).strip()
            payloads.append(
                ChunkPayload(
                    content=content,
                    excerpt=content[:280].strip(),
                    page_number=segment.page_number,
                    section_title=segment.section_title,
                )
            )
            start += step

    return payloads


class IngestionService:
    def __init__(self, ollama_service: OllamaService | None = None) -> None:
        self.ollama = ollama_service or OllamaService()

    def process(self, db: Session, document_id: UUID, job_id: UUID) -> None:
        document = db.get(Document, document_id)
        job = db.get(IngestionJob, job_id)
        if document is None or job is None:
            raise IngestionError("Nie znaleziono dokumentu albo zadania przetwarzania.")

        job.status = JobStatus.processing.value
        job.started_at = utcnow()
        document.status = DocumentStatus.processing.value
        document.error_message = None
        db.add_all([document, job])
        db.commit()

        try:
            chunks = self._build_chunks(Path(document.storage_path), document.format)
            embeddings = self.ollama.embed_texts([chunk.content for chunk in chunks])
            if len(embeddings) != len(chunks):
                raise IngestionError("Liczba embeddingów nie zgadza się z liczbą chunków.")

            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
            for index, payload in enumerate(chunks):
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=index,
                        content=payload.content,
                        citation_excerpt=payload.excerpt,
                        page_number=payload.page_number,
                        section_title=payload.section_title,
                        embedding=embeddings[index],
                    )
                )

            document.status = DocumentStatus.ready.value
            document.chunk_count = len(chunks)
            document.last_indexed_at = utcnow()
            document.error_message = None
            job.status = JobStatus.completed.value
            job.error_message = None
            job.finished_at = utcnow()
            db.add_all([document, job])
            db.commit()
        except Exception as exc:
            db.rollback()
            document = db.get(Document, document_id)
            job = db.get(IngestionJob, job_id)
            if document is not None:
                document.status = DocumentStatus.failed.value
                document.error_message = str(exc)
                db.add(document)
            if job is not None:
                job.status = JobStatus.failed.value
                job.error_message = str(exc)
                job.finished_at = utcnow()
                db.add(job)
            db.commit()
            raise

    def _build_chunks(self, path: Path, file_format: str) -> list[ChunkPayload]:
        segments = self._extract_segments(path, file_format)
        if not segments:
            raise IngestionError("Nie udało się wyodrębnić tekstu z dokumentu.")
        chunks = chunk_segments(segments)
        if not chunks:
            raise IngestionError("Nie udało się utworzyć chunków z dokumentu.")
        return chunks

    def _extract_segments(self, path: Path, file_format: str) -> list[ExtractedSegment]:
        file_format = file_format.lower()
        if file_format == "pdf":
            return self._extract_pdf(path)
        if file_format == "docx":
            return self._extract_docx(path)
        if file_format == "doc":
            return self._extract_doc(path)
        if file_format == "txt":
            return self._extract_txt(path)
        raise IngestionError(f"Nieobsługiwany format pliku: {file_format}")

    def _extract_pdf(self, path: Path) -> list[ExtractedSegment]:
        reader = PdfReader(str(path))
        segments: list[ExtractedSegment] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = normalize_text(page.extract_text() or "")
            if text:
                segments.append(ExtractedSegment(text=text, page_number=page_number))
        if not segments:
            raise ScannedDocumentError("PDF wygląda na skan albo dokument obrazkowy. OCR nie jest dostępny w wersji v1.")
        return segments

    def _extract_docx(self, path: Path) -> list[ExtractedSegment]:
        document = DocxDocument(str(path))
        segments: list[ExtractedSegment] = []
        section_title: str | None = None
        buffer: list[str] = []

        def flush() -> None:
            if buffer:
                segments.append(
                    ExtractedSegment(text=normalize_text(" ".join(buffer)), section_title=section_title)
                )
                buffer.clear()

        for paragraph in document.paragraphs:
            text = normalize_text(paragraph.text)
            if not text:
                continue
            style_name = getattr(paragraph.style, "name", "") or ""
            if style_name.lower().startswith("heading"):
                flush()
                section_title = text
                continue
            buffer.append(text)

        flush()
        if not segments:
            raise IngestionError("Dokument DOCX nie zawiera tekstu możliwego do odczytu.")
        return segments

    def _extract_doc(self, path: Path) -> list[ExtractedSegment]:
        with tempfile.TemporaryDirectory() as temp_dir:
            command = [
                "soffice",
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                temp_dir,
                str(path),
            ]
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:
                raise IngestionError(f"Nie udało się przekonwertować starszego pliku DOC: {exc.stderr or exc.stdout}") from exc

            converted_path = Path(temp_dir) / f"{path.stem}.docx"
            if not converted_path.exists():
                raise IngestionError("Konwersja starszego pliku DOC nie utworzyła pliku DOCX.")
            return self._extract_docx(converted_path)

    def _extract_txt(self, path: Path) -> list[ExtractedSegment]:
        content = path.read_text(encoding="utf-8", errors="ignore")
        normalized = normalize_text(content)
        if not normalized:
            raise IngestionError("Plik TXT nie zawiera tekstu możliwego do odczytu.")
        return [ExtractedSegment(text=normalized)]

