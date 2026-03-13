from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.core.config import get_settings
from app.models.entities import ChatAnswerStatus
from app.schemas.api import CitationResponse
from app.services.ollama import OllamaChatDiagnostics, OllamaService
from app.services.retrieval import RetrievalDiagnostics, RetrievalService

settings = get_settings()


@dataclass(slots=True)
class ChatDiagnostics:
    total_ms: float
    question_chars: int
    answer_chars: int
    evidence_count: int
    status: str
    retrieval: RetrievalDiagnostics
    ollama: OllamaChatDiagnostics | None


@dataclass(slots=True)
class AnswerResult:
    answer: str
    citations: list[CitationResponse]
    status: str
    diagnostics: ChatDiagnostics


class ChatService:
    def __init__(self) -> None:
        self.ollama = OllamaService()
        self.retrieval = RetrievalService(self.ollama)

    def answer(self, db, question: str) -> AnswerResult:
        started = perf_counter()
        evidence, retrieval_diagnostics = self._retrieve_with_diagnostics(db, question)
        if not evidence or evidence[0].score < settings.rag_score_threshold:
            answer = "Nie wiem na podstawie przesłanych dokumentów."
            return AnswerResult(
                answer=answer,
                citations=[],
                status=ChatAnswerStatus.insufficient_evidence.value,
                diagnostics=ChatDiagnostics(
                    total_ms=(perf_counter() - started) * 1000,
                    question_chars=len(question),
                    answer_chars=len(answer),
                    evidence_count=len(evidence),
                    status=ChatAnswerStatus.insufficient_evidence.value,
                    retrieval=retrieval_diagnostics,
                    ollama=None,
                ),
            )

        answer, ollama_diagnostics = self._grounded_answer_with_diagnostics(question, [item.to_prompt() for item in evidence])
        if answer.strip() == "Nie wiem na podstawie przesłanych dokumentów.":
            return AnswerResult(
                answer=answer,
                citations=[],
                status=ChatAnswerStatus.insufficient_evidence.value,
                diagnostics=ChatDiagnostics(
                    total_ms=(perf_counter() - started) * 1000,
                    question_chars=len(question),
                    answer_chars=len(answer),
                    evidence_count=len(evidence),
                    status=ChatAnswerStatus.insufficient_evidence.value,
                    retrieval=retrieval_diagnostics,
                    ollama=ollama_diagnostics,
                ),
            )

        citations = [
            CitationResponse(
                document_id=item.document_id,
                filename=item.filename,
                page=item.page_number,
                section=item.section_title,
                excerpt=item.excerpt,
            )
            for item in evidence
        ]
        return AnswerResult(
            answer=answer,
            citations=citations,
            status=ChatAnswerStatus.answered.value,
            diagnostics=ChatDiagnostics(
                total_ms=(perf_counter() - started) * 1000,
                question_chars=len(question),
                answer_chars=len(answer),
                evidence_count=len(evidence),
                status=ChatAnswerStatus.answered.value,
                retrieval=retrieval_diagnostics,
                ollama=ollama_diagnostics,
            ),
        )

    def _retrieve_with_diagnostics(self, db, question: str) -> tuple[list[Any], RetrievalDiagnostics]:
        if hasattr(self.retrieval, "retrieve_with_diagnostics"):
            return self.retrieval.retrieve_with_diagnostics(db, question)

        evidence = self.retrieval.retrieve(db, question)
        top_score = evidence[0].score if evidence else None
        return evidence, RetrievalDiagnostics.empty(returned_evidence_count=len(evidence), top_score=top_score)

    def _grounded_answer_with_diagnostics(self, question: str, evidence: list[Any]) -> tuple[str, OllamaChatDiagnostics]:
        if hasattr(self.ollama, "grounded_answer_with_diagnostics"):
            return self.ollama.grounded_answer_with_diagnostics(question, evidence)

        answer = self.ollama.grounded_answer(question, evidence)
        return answer, OllamaChatDiagnostics(
            http_ms=0.0,
            context_chars=0,
            response_chars=len(answer),
            total_duration_ms=None,
            load_duration_ms=None,
            prompt_eval_duration_ms=None,
            eval_duration_ms=None,
            prompt_eval_count=None,
            eval_count=None,
            done_reason=None,
        )

