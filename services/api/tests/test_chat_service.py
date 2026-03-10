from app.services.chat import ChatService
from app.models.entities import ChatAnswerStatus


class StubRetrievalService:
    def __init__(self, evidence):
        self.evidence = evidence

    def retrieve(self, db, query):
        return self.evidence


class StubOllamaService:
    def __init__(self, answer):
        self.answer = answer

    def grounded_answer(self, question, evidence):
        return self.answer


def test_chat_service_returns_insufficient_evidence_without_hits():
    service = ChatService()
    service.retrieval = StubRetrievalService([])

    result = service.answer(db=None, question="What is the refund policy?")

    assert result.status == ChatAnswerStatus.insufficient_evidence.value
    assert result.citations == []
    assert "uploaded documents" in result.answer


def test_chat_service_returns_citations_when_evidence_exists():
    class Evidence:
        document_id = "doc-1"
        filename = "policy.pdf"
        page_number = 2
        section_title = None
        excerpt = "Refunds are possible within seven days."
        score = 0.92

        def to_prompt(self):
            return self

        content = "Refunds are possible within seven days with proof of purchase."

    service = ChatService()
    service.retrieval = StubRetrievalService([Evidence()])
    service.ollama = StubOllamaService("Refunds are possible within seven days with proof of purchase.")

    result = service.answer(db=None, question="Can customers get a refund?")

    assert result.status == "answered"
    assert len(result.citations) == 1
    assert result.citations[0].filename == "policy.pdf"
