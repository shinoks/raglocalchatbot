from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=secret, salt="rag-admin-session")


def build_session_token(secret: str, admin_id: str) -> str:
    return _serializer(secret).dumps({"admin_id": admin_id})


def read_session_token(secret: str, token: str, max_age_seconds: int) -> str | None:
    try:
        payload = _serializer(secret).loads(token, max_age=max_age_seconds)
    except (BadSignature, BadTimeSignature):
        return None
    admin_id = payload.get("admin_id")
    if not isinstance(admin_id, str):
        return None
    return admin_id
