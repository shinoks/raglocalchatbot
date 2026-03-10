from __future__ import annotations

from dataclasses import dataclass

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


class OllamaService:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=settings.ollama_request_timeout_seconds)

    def healthcheck(self) -> None:
        with self._client() as client:
            response = client.get("/api/tags")
            response.raise_for_status()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        with self._client() as client:
            response = client.post(
                "/api/embed",
                json={"model": settings.ollama_embedding_model, "input": texts},
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
                    raise OllamaError("Ollama embedding response was malformed.")
                return [embedding]
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings")
            if not isinstance(embeddings, list):
                raise OllamaError("Ollama embedding response was malformed.")
            return embeddings

    def grounded_answer(self, question: str, evidence: list[EvidencePrompt]) -> str:
        context_blocks = []
        for index, item in enumerate(evidence, start=1):
            location_bits = []
            if item.page_number is not None:
                location_bits.append(f"page {item.page_number}")
            if item.section_title:
                location_bits.append(f"section {item.section_title}")
            location = ", ".join(location_bits) if location_bits else "location unavailable"
            context_blocks.append(
                f"[{index}] Document: {item.filename}\nLocation: {location}\nExcerpt: {item.excerpt}\nContent: {item.content}"
            )

        system_prompt = (
            "You are a retrieval-grounded assistant. Answer using only the provided context. "
            "If the context is insufficient, respond with exactly: I do not know based on the uploaded documents. "
            "Do not invent citations or facts."
        )
        user_prompt = "\n\n".join(context_blocks) + f"\n\nQuestion: {question}"

        with self._client() as client:
            response = client.post(
                "/api/chat",
                json={
                    "model": settings.ollama_chat_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "options": {"temperature": 0.1},
                },
            )
            response.raise_for_status()
            data = response.json()
            message = data.get("message", {})
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise OllamaError("Ollama chat response was empty.")
            return content.strip()
