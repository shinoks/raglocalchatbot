import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "RAG Chatbot API"
    database_url: str = "postgresql+psycopg://ragchat:ragchat@postgres:5432/ragchat"
    redis_url: str = "redis://redis:6379/0"
    ollama_base_url: str = "http://ollama:11434"
    ollama_chat_model: str = "llama3.2:1b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_request_timeout_seconds: float = 300.0
    embedding_dimension: int = 768
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me"
    session_secret: str = "local-session-secret"
    site_key: str = "local-demo-key"
    allowed_widget_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:4174", "http://localhost:8080"])
    upload_dir: Path = Path("storage/uploads")
    max_upload_bytes: int = 25 * 1024 * 1024
    public_rate_limit_per_minute: int = 30
    rag_score_threshold: float = 0.35
    rag_top_k: int = 6
    admin_cookie_name: str = "rag_admin_session"
    admin_session_max_age_seconds: int = 60 * 60 * 12
    admin_dev_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4173"])

    @staticmethod
    def _parse_origin_list(value: object, fallback: list[str]) -> list[str]:
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return fallback
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    origins = [str(item).strip() for item in parsed if str(item).strip()]
                    return origins or fallback
            origins = [item.strip() for item in raw.split(",") if item.strip()]
            return origins or fallback
        if isinstance(value, list):
            origins = [str(item).strip() for item in value if str(item).strip()]
            return origins or fallback
        return fallback

    @field_validator("allowed_widget_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> list[str]:
        return cls._parse_origin_list(value, ["http://localhost:3000", "http://localhost:4174", "http://localhost:8080"])

    @field_validator("admin_dev_origins", mode="before")
    @classmethod
    def split_admin_origins(cls, value: object) -> list[str]:
        return cls._parse_origin_list(value, ["http://localhost:4173"])

    @property
    def cors_origins(self) -> list[str]:
        return sorted(set(self.allowed_widget_origins + self.admin_dev_origins))


@lru_cache
def get_settings() -> Settings:
    return Settings()
