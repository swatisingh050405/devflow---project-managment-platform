
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
import hashlib
import jwt

from app.api.routes import auth as auth_routes
from app.core.config import settings
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.password_reset_token import PasswordResetToken


# ---------- HELPERS ----------

def create_user(client, email="test@example.com"):
    return client.post("/users/", json={
        "name": "Test User",
        "email": email,
        "password": "test123456"
    })


def login(client, email="test@example.com", password="test123456"):
    return client.post("/users/login", data={
        "username": email,
        "password": password
    })


def get_refresh_cookie(response):
    return response.cookies.get("refresh_token")


def get_reset_token_from_link(link):
    return parse_qs(urlparse(link).query)["token"][0]


def create_reset_token(db, user):
    raw_token = "test-reset-token"

    token_hash = hashlib.sha256(
        raw_token.encode()
    ).hexdigest()

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
    )

    db.add(reset_token)
    db.commit()

    return raw_token, reset_token


# ---------- REFRESH TOKEN TESTS ----------

def test_refresh_token_success(client):
    create_user(client)
    login_response = login(client)

    refresh_cookie = get_refresh_cookie(login_response)

    response = client.post(
        "/auth/refresh",
        cookies={"refresh_token": refresh_cookie}
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"
    assert get_refresh_cookie(response) is not None


def test_refresh_without_cookie(client):
    response = client.post("/auth/refresh")

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token missing"


def test_refresh_with_invalid_token(client):
    response = client.post(
        "/auth/refresh",
        cookies={"refresh_token": "invalid-token"}
    )

    assert response.status_code == 401


def test_refresh_with_access_token(client):
    create_user(client)
    login_response = login(client)

    access_token = login_response.json()["access_token"]

    response = client.post(
        "/auth/refresh",
        cookies={"refresh_token": access_token}
    )

    assert response.status_code == 401


def test_old_refresh_token_revoked_after_rotation(client, db):
    create_user(client)
    login_response = login(client)

    old_refresh_token = get_refresh_cookie(login_response)

    first_response = client.post(
        "/auth/refresh",
        cookies={"refresh_token": old_refresh_token}
    )

    assert first_response.status_code == 200

    payload = jwt.decode(
        old_refresh_token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
    )

    old_session = db.query(RefreshToken).filter(
        RefreshToken.jti == payload["jti"]
    ).first()

    assert old_session.revoked is True

    second_response = client.post(
        "/auth/refresh",
        cookies={"refresh_token": old_refresh_token}
    )

    assert second_response.status_code == 401


def test_refresh_revoked_token(client):
    create_user(client)
    login_response = login(client)

    refresh_cookie = get_refresh_cookie(login_response)

    client.post(
        "/auth/logout",
        cookies={"refresh_token": refresh_cookie}
    )

    response = client.post(
        "/auth/refresh",
        cookies={"refresh_token": refresh_cookie}
    )

    assert response.status_code == 401


# ---------- LOGOUT TESTS ----------

def test_logout_success(client, db):
    create_user(client)
    login_response = login(client)

    refresh_cookie = get_refresh_cookie(login_response)

    payload = jwt.decode(
        refresh_cookie,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
    )

    response = client.post(
        "/auth/logout",
        cookies={"refresh_token": refresh_cookie}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"

    session = db.query(RefreshToken).filter(
        RefreshToken.jti == payload["jti"]
    ).first()

    assert session.revoked is True


def test_logout_without_cookie(client):
    response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"


def test_logout_with_invalid_token(client):
    response = client.post(
        "/auth/logout",
        cookies={"refresh_token": "invalid-token"}
    )

    assert response.status_code == 200


# ---------- FORGOT PASSWORD TESTS ----------

def test_forgot_password_unknown_email(client):
    response = client.post(
        "/auth/forgot-password",
        json={"email": "unknown@example.com"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == (
        "If the email is registered, a reset link will be sent."
    )


def test_forgot_password_registered_email(client, db, monkeypatch):
    create_user(client)

    captured = {}

    def fake_send_email(email, reset_link):
        captured["email"] = email
        captured["reset_link"] = reset_link

    monkeypatch.setattr(
        auth_routes,
        "send_password_reset_email",
        fake_send_email
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": "test@example.com"}
    )

    assert response.status_code == 200
    assert captured["email"] == "test@example.com"

    raw_token = get_reset_token_from_link(
        captured["reset_link"]
    )

    token_hash = hashlib.sha256(
        raw_token.encode()
    ).hexdigest()

    saved_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash
    ).first()

    assert saved_token is not None
    assert saved_token.used is False


def test_forgot_password_invalidates_previous_token(
    client, db, monkeypatch
):
    create_user(client)

    captured = []

    def fake_send_email(email, reset_link):
        captured.append(reset_link)

    monkeypatch.setattr(
        auth_routes,
        "send_password_reset_email",
        fake_send_email
    )

    client.post(
        "/auth/forgot-password",
        json={"email": "test@example.com"}
    )

    first_token = get_reset_token_from_link(captured[0])

    client.post(
        "/auth/forgot-password",
        json={"email": "test@example.com"}
    )

    second_token = get_reset_token_from_link(captured[1])

    first_hash = hashlib.sha256(
        first_token.encode()
    ).hexdigest()

    second_hash = hashlib.sha256(
        second_token.encode()
    ).hexdigest()

    first_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == first_hash
    ).first()

    second_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == second_hash
    ).first()

    assert first_record.used is True
    assert second_record.used is False


# ---------- RESET PASSWORD TESTS ----------

def test_reset_password_success(client, db):
    create_user(client)

    user = db.query(User).filter(
        User.email == "test@example.com"
    ).first()

    raw_token, reset_record = create_reset_token(db, user)

    response = client.post(
        "/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "newpassword123"
        }
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Password reset successful"
    assert reset_record.used is True

    old_login = login(client, password="test123456")
    new_login = login(client, password="newpassword123")

    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_reset_password_invalid_token(client):
    response = client.post(
        "/auth/reset-password",
        json={
            "token": "invalid-token",
            "new_password": "newpassword123"
        }
    )

    assert response.status_code == 400


def test_reset_password_expired_token(client, db):
    create_user(client)

    user = db.query(User).filter(
        User.email == "test@example.com"
    ).first()

    raw_token, reset_record = create_reset_token(db, user)

    reset_record.expires_at = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    db.commit()

    response = client.post(
        "/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "newpassword123"
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Reset token has expired"


def test_reset_password_token_cannot_be_reused(client, db):
    create_user(client)

    user = db.query(User).filter(
        User.email == "test@example.com"
    ).first()

    raw_token, reset_record = create_reset_token(db, user)

    data = {
        "token": raw_token,
        "new_password": "newpassword123"
    }

    first_response = client.post(
        "/auth/reset-password",
        json=data
    )

    second_response = client.post(
        "/auth/reset-password",
        json=data
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 400


def test_reset_password_revokes_refresh_sessions(client, db):
    create_user(client)

    login_response = login(client)
    refresh_cookie = get_refresh_cookie(login_response)

    user = db.query(User).filter(
        User.email == "test@example.com"
    ).first()

    raw_token, reset_record = create_reset_token(db, user)

    response = client.post(
        "/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "newpassword123"
        }
    )

    assert response.status_code == 200

    active_sessions = db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked == False
    ).all()

    assert len(active_sessions) == 0

    refresh_response = client.post(
        "/auth/refresh",
        cookies={"refresh_token": refresh_cookie}
    )

    assert refresh_response.status_code == 401


def test_reset_password_short_password(client, db):
    create_user(client)

    user = db.query(User).filter(
        User.email == "test@example.com"
    ).first()

    raw_token, reset_record = create_reset_token(db, user)

    response = client.post(
        "/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "short"
        }
    )

    assert response.status_code == 422
