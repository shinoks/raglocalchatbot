from app.core.security import build_session_token, read_session_token


def test_session_token_round_trip():
    token = build_session_token("secret", "admin-123")

    assert read_session_token("secret", token, 60) == "admin-123"


def test_session_token_rejects_wrong_secret():
    token = build_session_token("secret", "admin-123")

    assert read_session_token("other-secret", token, 60) is None
