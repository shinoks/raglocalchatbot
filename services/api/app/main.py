from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.routes.admin_auth import router as admin_auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.admin import ensure_admin_user
from app.services.ollama import OllamaService

settings = get_settings()
logger = logging.getLogger("uvicorn.error")


def preload_ollama_models() -> None:
    if not settings.ollama_preload_models_on_startup:
        return

    service = OllamaService()
    attempts = 12
    for attempt in range(1, attempts + 1):
        try:
            service.preload_embedding_model()
            service.preload_chat_model()
            logger.info(
                "Preloaded Ollama models: chat=%s embed=%s",
                settings.ollama_chat_model,
                settings.ollama_embedding_model,
            )
            return
        except Exception as exc:
            if attempt == attempts:
                logger.warning("Ollama preload failed after %s attempts: %s", attempts, exc)
                return
            time.sleep(1)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as session:
        try:
            ensure_admin_user(session)
        except Exception:
            session.rollback()
    preload_ollama_models()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(admin_auth_router)
app.include_router(documents_router)
app.include_router(chat_router)


def run() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
