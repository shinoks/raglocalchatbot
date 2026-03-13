from app.core.security import verify_password
from app.models.entities import AdminUser
from app.services import admin as admin_service


class StubSession:
    def __init__(self, admin: AdminUser | None) -> None:
        self.admin = admin
        self.add_calls = 0
        self.commit_calls = 0
        self.refresh_calls = 0

    def scalar(self, _query):
        return self.admin

    def add(self, admin: AdminUser) -> None:
        self.add_calls += 1
        self.admin = admin

    def commit(self) -> None:
        self.commit_calls += 1

    def refresh(self, _admin: AdminUser) -> None:
        self.refresh_calls += 1


def test_ensure_admin_user_creates_admin_when_missing(monkeypatch):
    monkeypatch.setattr(admin_service.settings, "admin_email", "admin@example.com")
    monkeypatch.setattr(admin_service.settings, "admin_password", "change-me")
    session = StubSession(admin=None)

    admin = admin_service.ensure_admin_user(session)

    assert admin.email == "admin@example.com"
    assert verify_password("change-me", admin.password_hash)
    assert session.add_calls == 1
    assert session.commit_calls == 1
    assert session.refresh_calls == 1


def test_ensure_admin_user_does_not_reset_existing_password(monkeypatch):
    monkeypatch.setattr(admin_service.settings, "admin_email", "admin@example.com")
    monkeypatch.setattr(admin_service.settings, "admin_password", "new-password-from-env")
    existing_admin = AdminUser(
        email="admin@example.com",
        password_hash=admin_service.hash_password("existing-password"),
    )
    original_hash = existing_admin.password_hash
    session = StubSession(admin=existing_admin)

    admin = admin_service.ensure_admin_user(session)

    assert admin is existing_admin
    assert admin.password_hash == original_hash
    assert verify_password("existing-password", admin.password_hash)
    assert not verify_password("new-password-from-env", admin.password_hash)
    assert session.add_calls == 0
    assert session.commit_calls == 0
    assert session.refresh_calls == 0
