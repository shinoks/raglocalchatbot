from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import httpx

from app.core.config import get_settings

settings = get_settings()


class OllamaError(RuntimeError):
    pass


@dataclass(slots=True)
class EvidencePrompt:
    filename: str
    excerpt: str
    page_number: int | None
    section_title: str | None
    content: str
    score: float


@dataclass(slots=True)
class OllamaChatDiagnostics:
    http_ms: float
    context_chars: int
    response_chars: int
    total_duration_ms: float | None
    load_duration_ms: float | None
    prompt_eval_duration_ms: float | None
    eval_duration_ms: float | None
    prompt_eval_count: int | None
    eval_count: int | None
    done_reason: str | None


def _ns_to_ms(value: object) -> float | None:
    if isinstance(value, int):
        return value / 1_000_000
    return None


class OllamaService:
    def __init__(self) -> None:
        self.chat_base_url = settings.ollama_chat_base_url
        self.embedding_base_url = settings.ollama_effective_embedding_base_url

    def _client(self, base_url: str) -> httpx.Client:
        return httpx.Client(base_url=base_url, timeout=settings.ollama_request_timeout_seconds)

    def _keep_alive(self, value: str) -> str | int:
        raw = value.strip()
        if raw in {"-1", "0"}:
            return int(raw)
        return raw

    def _build_context_block(self, index: int, item: EvidencePrompt) -> str:
        location_bits = []
        if item.page_number is not None:
            location_bits.append(f"strona {item.page_number}")
        if item.section_title:
            location_bits.append(f"sekcja {item.section_title}")
        location = ", ".join(location_bits) if location_bits else "brak informacji o lokalizacji"
        return f"[{index}] Dokument: {item.filename}\nLokalizacja: {location}\nTreść: {item.content.strip()}"

    def _build_user_prompt(self, question: str, evidence: list[EvidencePrompt]) -> str:
        context_blocks: list[str] = []
        total_chars = 0

        for index, item in enumerate(evidence, start=1):
            block = self._build_context_block(index, item)
            next_total = total_chars + len(block) + 2
            if context_blocks and next_total > settings.rag_context_char_budget:
                break
            context_blocks.append(block)
            total_chars = next_total

        context = "\n\n".join(context_blocks)
        return f"Pytanie: {question}\n\nKontekst:\n{context}"

    def healthcheck(self) -> None:
        self.healthcheck_chat()
        self.healthcheck_embedding()

    def healthcheck_chat(self) -> None:
        with self._client(self.chat_base_url) as client:
            response = client.get("/api/tags")
            response.raise_for_status()

    def healthcheck_embedding(self) -> None:
        with self._client(self.embedding_base_url) as client:
            response = client.get("/api/tags")
            response.raise_for_status()

    def preload_chat_model(self) -> None:
        with self._client(self.chat_base_url) as client:
            response = client.post(
                "/api/generate",
                json={
                    "model": settings.ollama_chat_model,
                    "prompt": "",
                    "stream": False,
                    "keep_alive": self._keep_alive(settings.ollama_chat_keep_alive),
                },
            )
            response.raise_for_status()

    def preload_embedding_model(self) -> None:
        self.embed_texts(["warmup"])

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        with self._client(self.embedding_base_url) as client:
            response = client.post(
                "/api/embed",
                json={
                    "model": settings.ollama_embedding_model,
                    "input": texts,
                    "keep_alive": self._keep_alive(settings.ollama_embedding_keep_alive),
                },
            )
            if response.status_code == 404:
                fallback = client.post(
                    "/api/embeddings",
                    json={"model": settings.ollama_embedding_model, "prompt": texts[0]},
                )
                fallback.raise_for_status()
                data = fallback.json()
                embedding = data.get("embedding")
                if not isinstance(embedding, list):
                    raise OllamaError("Odpowiedź embeddingów z Ollama ma nieprawidłowy format.")
                return [embedding]
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings")
            if not isinstance(embeddings, list):
                raise OllamaError("Odpowiedź embeddingów z Ollama ma nieprawidłowy format.")
            return embeddings

    def grounded_answer(self, question: str, evidence: list[EvidencePrompt]) -> str:
        answer, _ = self.grounded_answer_with_diagnostics(question, evidence)
        return answer

    def grounded_answer_with_diagnostics(
        self, question: str, evidence: list[EvidencePrompt]
    ) -> tuple[str, OllamaChatDiagnostics]:
        system_prompt = (
            "Jesteś asystentem opartym na wyszukanym kontekście. Odpowiadaj w tym samym języku co pytanie i używaj wyłącznie dostarczonego kontekstu. "
            "Zacznij od bezpośredniej odpowiedzi. Odpowiedź ma być zwięzła i średniej długości: zwykle 2-5 zdań albo krótka lista punktowana, jeśli poprawia to czytelność. "
            "Jeśli pytanie dotyczy zasad, procedur, systemów, warunków, wyjątków albo ma kilka części, uwzględnij wszystkie istotne informacje z kontekstu, ale bez powtórzeń i zbędnego rozwijania. "
            "Podawaj liczby, daty, zasady, warunki i wyjątki tylko wtedy, gdy wynikają wprost z kontekstu. "
            "Jeśli kontekst jest niewystarczający, odpowiedz dokładnie: Nie wiem na podstawie przesłanych dokumentów. "
            "Nie wymyślaj cytowań ani faktów."
        )
        user_prompt = self._build_user_prompt(question, evidence)

        with self._client(self.chat_base_url) as client:
            started = perf_counter()
            response = client.post(
                "/api/chat",
                json={
                    "model": settings.ollama_chat_model,
                    "stream": False,
                    "keep_alive": self._keep_alive(settings.ollama_chat_keep_alive),
                    "think": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "options": {"temperature": 0.1, "num_predict": settings.ollama_chat_num_predict},
                },
            )
            http_ms = (perf_counter() - started) * 1000
            response.raise_for_status()
            data = response.json()
            message = data.get("message", {})
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise OllamaError("Odpowiedź czatu z Ollama jest pusta.")
            answer = content.strip()
            diagnostics = OllamaChatDiagnostics(
                http_ms=http_ms,
                context_chars=len(user_prompt),
                response_chars=len(answer),
                total_duration_ms=_ns_to_ms(data.get("total_duration")),
                load_duration_ms=_ns_to_ms(data.get("load_duration")),
                prompt_eval_duration_ms=_ns_to_ms(data.get("prompt_eval_duration")),
                eval_duration_ms=_ns_to_ms(data.get("eval_duration")),
                prompt_eval_count=data.get("prompt_eval_count") if isinstance(data.get("prompt_eval_count"), int) else None,
                eval_count=data.get("eval_count") if isinstance(data.get("eval_count"), int) else None,
                done_reason=data.get("done_reason") if isinstance(data.get("done_reason"), str) else None,
            )
            return answer, diagnostics



