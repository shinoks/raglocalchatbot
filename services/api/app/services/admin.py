from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models.entities import AdminUser

settings = get_settings()


def ensure_admin_user(session: Session) -> AdminUser:
    admin = session.scalar(select(AdminUser).where(AdminUser.email == settings.admin_email))

    if admin is None:
        admin = AdminUser(email=settings.admin_email, password_hash=hash_password(settings.admin_password))
        session.add(admin)
        session.commit()
        session.refresh(admin)

    return admin


def authenticate_admin(session: Session, email: str, password: str) -> AdminUser | None:
    admin = session.scalar(select(AdminUser).where(AdminUser.email == email))
    if admin is None:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    return admin
