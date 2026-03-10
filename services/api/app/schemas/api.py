from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    created_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    checksum: str
    format: str
    status: str
    chunk_count: int
    last_indexed_at: datetime | None
    uploaded_at: datetime
    error_message: str | None


class CitationResponse(BaseModel):
    document_id: UUID
    filename: str
    page: int | None
    section: str | None
    excerpt: str


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    job_type: str
    status: str
    error_message: str | None
    queue_job_id: str | None
    enqueued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CreateSessionResponse(BaseModel):
    session_id: UUID


class ChatMessageRequest(BaseModel):
    session_id: UUID
    message: str


class ChatResponse(BaseModel):
    session_id: UUID
    answer: str
    citations: list[CitationResponse]
    status: str


class HealthComponent(BaseModel):
    ok: bool
    detail: str | None = None


class HealthResponse(BaseModel):
    api: HealthComponent
    postgres: HealthComponent
    redis: HealthComponent
    ollama: HealthComponent
