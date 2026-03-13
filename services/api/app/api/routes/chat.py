from datetime import datetime, timezone
import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import enforce_public_rate_limit, require_widget_access
from app.db.session import get_db
from app.models.entities import ChatMessage, ChatMessageRole, ChatSession
from app.schemas.api import ChatMessageRequest, ChatResponse, CreateSessionResponse
from app.services.chat import ChatDiagnostics, ChatService
from app.services.ollama import OllamaError

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger("uvicorn.error")


MODEL_UNAVAILABLE_DETAIL = "Model lokalny nadal się uruchamia albo odpowiada zbyt długo. Spróbuj ponownie za chwilę."


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _timing_metric(name: str, value: float | None) -> str | None:
    if value is None:
        return None
    return f"{name};dur={value:.1f}"


def _server_timing_header(diagnostics: ChatDiagnostics) -> str:
    metrics = [
        _timing_metric("api_total", diagnostics.total_ms),
        _timing_metric("retrieve", diagnostics.retrieval.total_ms),
        _timing_metric("embed", diagnostics.retrieval.embed_ms),
        _timing_metric("vector", diagnostics.retrieval.vector_search_ms),
        _timing_metric("fts", diagnostics.retrieval.full_text_search_ms),
        _timing_metric("merge", diagnostics.retrieval.merge_ms),
    ]
    if diagnostics.ollama is not None:
        metrics.extend(
            [
                _timing_metric("ollama_http", diagnostics.ollama.http_ms),
                _timing_metric("ollama_total", diagnostics.ollama.total_duration_ms),
                _timing_metric("load", diagnostics.ollama.load_duration_ms),
                _timing_metric("prompt_eval", diagnostics.ollama.prompt_eval_duration_ms),
                _timing_metric("eval", diagnostics.ollama.eval_duration_ms),
            ]
        )
    return ", ".join(metric for metric in metrics if metric is not None)


def _log_chat_timing(session_id: str, diagnostics: ChatDiagnostics) -> None:
    payload = {
        "event": "chat_timing",
        "session_id": session_id,
        "status": diagnostics.status,
        "total_ms": round(diagnostics.total_ms, 1),
        "question_chars": diagnostics.question_chars,
        "answer_chars": diagnostics.answer_chars,
        "evidence_count": diagnostics.evidence_count,
        "top_score": None if diagnostics.retrieval.top_score is None else round(diagnostics.retrieval.top_score, 4),
        "embedding_dimensions": diagnostics.retrieval.embedding_dimensions,
        "embed_ms": round(diagnostics.retrieval.embed_ms, 1),
        "vector_search_ms": round(diagnostics.retrieval.vector_search_ms, 1),
        "full_text_search_ms": round(diagnostics.retrieval.full_text_search_ms, 1),
        "merge_ms": round(diagnostics.retrieval.merge_ms, 1),
        "retrieve_total_ms": round(diagnostics.retrieval.total_ms, 1),
        "vector_candidate_count": diagnostics.retrieval.vector_candidate_count,
        "full_text_candidate_count": diagnostics.retrieval.full_text_candidate_count,
        "returned_evidence_count": diagnostics.retrieval.returned_evidence_count,
    }
    if diagnostics.ollama is not None:
        payload.update(
            {
                "ollama_http_ms": round(diagnostics.ollama.http_ms, 1),
                "ollama_total_duration_ms": None
                if diagnostics.ollama.total_duration_ms is None
                else round(diagnostics.ollama.total_duration_ms, 1),
                "ollama_load_duration_ms": None
                if diagnostics.ollama.load_duration_ms is None
                else round(diagnostics.ollama.load_duration_ms, 1),
                "ollama_prompt_eval_duration_ms": None
                if diagnostics.ollama.prompt_eval_duration_ms is None
                else round(diagnostics.ollama.prompt_eval_duration_ms, 1),
                "ollama_eval_duration_ms": None
                if diagnostics.ollama.eval_duration_ms is None
                else round(diagnostics.ollama.eval_duration_ms, 1),
                "ollama_prompt_eval_count": diagnostics.ollama.prompt_eval_count,
                "ollama_eval_count": diagnostics.ollama.eval_count,
                "ollama_context_chars": diagnostics.ollama.context_chars,
                "ollama_done_reason": diagnostics.ollama.done_reason,
            }
        )
    print(f"chat_timing {json.dumps(payload, ensure_ascii=False, sort_keys=True)}", flush=True)


@router.post("/sessions", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    request: Request,
    db: Session = Depends(get_db),
) -> CreateSessionResponse:
    require_widget_access(request)
    client_ip = enforce_public_rate_limit(request)

    session = ChatSession(
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return CreateSessionResponse(session_id=session.id)


@router.post("/messages", response_model=ChatResponse)
def send_message(
    payload: ChatMessageRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ChatResponse:
    require_widget_access(request)
    enforce_public_rate_limit(request)

    if not payload.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wiadomość nie może być pusta.")

    session = db.get(ChatSession, payload.session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nie znaleziono sesji.")

    session.last_seen_at = utcnow()
    db.add(session)
    db.add(ChatMessage(session_id=session.id, role=ChatMessageRole.user.value, content=payload.message.strip()))
    db.commit()

    try:
        result = ChatService().answer(db, payload.message.strip())
    except (httpx.TimeoutException, OllamaError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=MODEL_UNAVAILABLE_DETAIL) from exc

    response.headers["Server-Timing"] = _server_timing_header(result.diagnostics)
    _log_chat_timing(str(session.id), result.diagnostics)

    db.add(
        ChatMessage(
            session_id=session.id,
            role=ChatMessageRole.assistant.value,
            content=result.answer,
            status=result.status,
        )
    )
    db.commit()

    return ChatResponse(
        session_id=session.id,
        answer=result.answer,
        citations=result.citations,
        status=result.status,
    )



