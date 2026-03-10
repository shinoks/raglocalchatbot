from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import read_session_token
from app.db.session import get_db
from app.models.entities import AdminUser
from app.services.rate_limit import RateLimitService

settings = get_settings()


def current_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_admin(
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=settings.admin_cookie_name),
) -> AdminUser:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    admin_id = read_session_token(
        settings.session_secret,
        session_token,
        settings.admin_session_max_age_seconds,
    )
    if admin_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.")

    admin = db.scalar(select(AdminUser).where(AdminUser.id == admin_id))
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.")
    return admin


def require_widget_access(request: Request) -> str:
    site_key = request.headers.get("x-site-key")
    if site_key != settings.site_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid site key.")

    origin = request.headers.get("origin")
    if origin not in settings.allowed_widget_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin is not allowed.")
    return origin


def enforce_public_rate_limit(request: Request) -> str:
    client_ip = get_client_ip(request)
    if not RateLimitService().allow(client_ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded.")
    return client_ip
