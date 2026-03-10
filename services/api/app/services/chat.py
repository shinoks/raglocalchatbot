from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.models.entities import ChatAnswerStatus
from app.schemas.api import CitationResponse
from app.services.ollama import OllamaService
from app.services.retrieval import RetrievalService

settings = get_settings()


@dataclass(slots=True)
class AnswerResult:
    answer: str
    citations: list[CitationResponse]
    status: str


class ChatService:
    def __init__(self) -> None:
        self.ollama = OllamaService()
        self.retrieval = RetrievalService(self.ollama)

    def answer(self, db, question: str) -> AnswerResult:
        evidence = self.retrieval.retrieve(db, question)
        if not evidence or evidence[0].score < settings.rag_score_threshold:
            return AnswerResult(
                answer="I do not know based on the uploaded documents.",
                citations=[],
                status=ChatAnswerStatus.insufficient_evidence.value,
            )

        answer = self.ollama.grounded_answer(question, [item.to_prompt() for item in evidence])
        if answer.strip() == "I do not know based on the uploaded documents.":
            return AnswerResult(
                answer=answer,
                citations=[],
                status=ChatAnswerStatus.insufficient_evidence.value,
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
        return AnswerResult(answer=answer, citations=citations, status=ChatAnswerStatus.answered.value)
