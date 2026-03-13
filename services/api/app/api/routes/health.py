from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.api import HealthComponent, HealthResponse
from app.services.ollama import OllamaService
from app.workers.queue import get_redis_connection

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    postgres = HealthComponent(ok=True)
    redis = HealthComponent(ok=True)
    ollama = HealthComponent(ok=True)

    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        postgres = HealthComponent(ok=False, detail=str(exc))

    try:
        get_redis_connection().ping()
    except Exception as exc:
        redis = HealthComponent(ok=False, detail=str(exc))

    service = OllamaService()
    ollama_errors: list[str] = []
    try:
        service.healthcheck_chat()
    except Exception as exc:
        ollama_errors.append(f"chat: {exc}")
    try:
        service.healthcheck_embedding()
    except Exception as exc:
        ollama_errors.append(f"embed: {exc}")
    if ollama_errors:
        ollama = HealthComponent(ok=False, detail="; ".join(ollama_errors))

    return HealthResponse(
        api=HealthComponent(ok=True),
        postgres=postgres,
        redis=redis,
        ollama=ollama,
    )
