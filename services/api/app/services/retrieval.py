from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.ollama import EvidencePrompt, OllamaService

settings = get_settings()


@dataclass(slots=True)
class EvidenceChunk:
    id: UUID
    document_id: UUID
    filename: str
    content: str
    excerpt: str
    page_number: int | None
    section_title: str | None
    score: float

    def to_prompt(self) -> EvidencePrompt:
        return EvidencePrompt(
            filename=self.filename,
            excerpt=self.excerpt,
            page_number=self.page_number,
            section_title=self.section_title,
            content=self.content,
            score=self.score,
        )


def _embedding_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


class RetrievalService:
    def __init__(self, ollama_service: OllamaService | None = None) -> None:
        self.ollama = ollama_service or OllamaService()

    def retrieve(self, session: Session, query: str) -> list[EvidenceChunk]:
        embedding = self.ollama.embed_texts([query])[0]
        vector_literal = _embedding_literal(embedding)

        vector_rows = session.execute(
            text(
                """
                SELECT
                  dc.id,
                  dc.document_id,
                  d.filename,
                  dc.content,
                  dc.citation_excerpt,
                  dc.page_number,
                  dc.section_title,
                  GREATEST(0.0, 1 - (dc.embedding <=> CAST(:embedding AS vector))) AS score
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE d.status = 'ready'
                ORDER BY dc.embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
                """
            ),
            {"embedding": vector_literal, "limit": settings.rag_top_k * 2},
        ).mappings()

        text_rows = session.execute(
            text(
                """
                SELECT
                  dc.id,
                  dc.document_id,
                  d.filename,
                  dc.content,
                  dc.citation_excerpt,
                  dc.page_number,
                  dc.section_title,
                  ts_rank_cd(
                    to_tsvector('english', dc.content),
                    websearch_to_tsquery('english', :query)
                  ) AS score
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE d.status = 'ready'
                  AND to_tsvector('english', dc.content) @@ websearch_to_tsquery('english', :query)
                ORDER BY score DESC
                LIMIT :limit
                """
            ),
            {"query": query, "limit": settings.rag_top_k * 2},
        ).mappings()

        merged: dict[UUID, EvidenceChunk] = {}
        for row in vector_rows:
            merged[row["id"]] = EvidenceChunk(
                id=row["id"],
                document_id=row["document_id"],
                filename=row["filename"],
                content=row["content"],
                excerpt=row["citation_excerpt"],
                page_number=row["page_number"],
                section_title=row["section_title"],
                score=float(row["score"]),
            )

        for row in text_rows:
            normalized = min(float(row["score"]), 1.0)
            if row["id"] in merged:
                merged[row["id"]].score = max(merged[row["id"]].score, normalized)
            else:
                merged[row["id"]] = EvidenceChunk(
                    id=row["id"],
                    document_id=row["document_id"],
                    filename=row["filename"],
                    content=row["content"],
                    excerpt=row["citation_excerpt"],
                    page_number=row["page_number"],
                    section_title=row["section_title"],
                    score=normalized,
                )

        ranked = sorted(merged.values(), key=lambda item: item.score, reverse=True)
        return ranked[: settings.rag_top_k]
