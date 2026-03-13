from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
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


@dataclass(slots=True)
class RetrievalDiagnostics:
    embed_ms: float
    vector_search_ms: float
    full_text_search_ms: float
    merge_ms: float
    total_ms: float
    embedding_dimensions: int
    vector_candidate_count: int
    full_text_candidate_count: int
    returned_evidence_count: int
    top_score: float | None

    @classmethod
    def empty(cls, returned_evidence_count: int = 0, top_score: float | None = None) -> "RetrievalDiagnostics":
        return cls(
            embed_ms=0.0,
            vector_search_ms=0.0,
            full_text_search_ms=0.0,
            merge_ms=0.0,
            total_ms=0.0,
            embedding_dimensions=0,
            vector_candidate_count=0,
            full_text_candidate_count=0,
            returned_evidence_count=returned_evidence_count,
            top_score=top_score,
        )


def _embedding_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


class RetrievalService:
    def __init__(self, ollama_service: OllamaService | None = None) -> None:
        self.ollama = ollama_service or OllamaService()

    def retrieve(self, session: Session, query: str) -> list[EvidenceChunk]:
        evidence, _ = self.retrieve_with_diagnostics(session, query)
        return evidence

    def retrieve_with_diagnostics(self, session: Session, query: str) -> tuple[list[EvidenceChunk], RetrievalDiagnostics]:
        total_started = perf_counter()
        embed_started = perf_counter()
        embedding = self.ollama.embed_texts([query])[0]
        embed_ms = (perf_counter() - embed_started) * 1000
        vector_literal = _embedding_literal(embedding)

        vector_started = perf_counter()
        vector_rows = list(
            session.execute(
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
        )
        vector_search_ms = (perf_counter() - vector_started) * 1000

        full_text_started = perf_counter()
        text_rows = list(
            session.execute(
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
                        to_tsvector('simple', dc.content),
                        websearch_to_tsquery('simple', :query)
                      ) AS score
                    FROM document_chunks dc
                    JOIN documents d ON d.id = dc.document_id
                    WHERE d.status = 'ready'
                      AND to_tsvector('simple', dc.content) @@ websearch_to_tsquery('simple', :query)
                    ORDER BY score DESC
                    LIMIT :limit
                    """
                ),
                {"query": query, "limit": settings.rag_top_k * 2},
            ).mappings()
        )
        full_text_search_ms = (perf_counter() - full_text_started) * 1000

        merge_started = perf_counter()
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
        returned = ranked[: settings.rag_top_k]
        merge_ms = (perf_counter() - merge_started) * 1000
        total_ms = (perf_counter() - total_started) * 1000
        diagnostics = RetrievalDiagnostics(
            embed_ms=embed_ms,
            vector_search_ms=vector_search_ms,
            full_text_search_ms=full_text_search_ms,
            merge_ms=merge_ms,
            total_ms=total_ms,
            embedding_dimensions=len(embedding),
            vector_candidate_count=len(vector_rows),
            full_text_candidate_count=len(text_rows),
            returned_evidence_count=len(returned),
            top_score=returned[0].score if returned else None,
        )
        return returned, diagnostics
