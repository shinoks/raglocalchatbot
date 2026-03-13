from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.config import get_settings
from app.core.security import build_session_token
from app.db.session import get_db
from app.models.entities import AdminUser
from app.schemas.api import AdminLoginRequest, AdminUserResponse
from app.services.admin import authenticate_admin

router = APIRouter(prefix="/api/admin", tags=["admin-auth"])
settings = get_settings()


@router.post("/login", response_model=AdminUserResponse)
def login(payload: AdminLoginRequest, response: Response, db: Session = Depends(get_db)) -> AdminUserResponse:
    admin = authenticate_admin(db, payload.email, payload.password)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieprawidłowe dane logowania.")

    token = build_session_token(settings.session_secret, str(admin.id))
    response.set_cookie(
        key=settings.admin_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.admin_session_max_age_seconds,
    )
    return admin


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(settings.admin_cookie_name)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AdminUserResponse)
def me(current_admin: AdminUser = Depends(require_admin)) -> AdminUserResponse:
    return current_admin

