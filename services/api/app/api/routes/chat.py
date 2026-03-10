from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import enforce_public_rate_limit, require_widget_access
from app.db.session import get_db
from app.models.entities import ChatMessage, ChatMessageRole, ChatSession
from app.schemas.api import ChatMessageRequest, ChatResponse, CreateSessionResponse
from app.services.chat import ChatService
from app.services.ollama import OllamaError

router = APIRouter(prefix="/api/chat", tags=["chat"])


MODEL_UNAVAILABLE_DETAIL = "The local model is still starting or took too long to respond. Please try again in a moment."


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    db: Session = Depends(get_db),
) -> ChatResponse:
    require_widget_access(request)
    enforce_public_rate_limit(request)

    if not payload.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message must not be empty.")

    session = db.get(ChatSession, payload.session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    session.last_seen_at = utcnow()
    db.add(session)
    db.add(ChatMessage(session_id=session.id, role=ChatMessageRole.user.value, content=payload.message.strip()))
    db.commit()

    try:
        result = ChatService().answer(db, payload.message.strip())
    except (httpx.TimeoutException, OllamaError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=MODEL_UNAVAILABLE_DETAIL) from exc

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
