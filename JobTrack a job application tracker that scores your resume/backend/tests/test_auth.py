import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.config import JWT_SECRET
from app.main import app
from app.models import Application, Reminder, Resume, StatusHistory, User

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db() -> None:
    db = SessionLocal()
    db.query(Resume).delete()
    db.query(StatusHistory).delete()
    db.query(Reminder).delete()
    db.query(Application).delete()
    db.query(User).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(Resume).delete()
    db.query(StatusHistory).delete()
    db.query(Reminder).delete()
    db.query(Application).delete()
    db.query(User).delete()
    db.commit()
    db.close()


def test_signup_success() -> None:
    response = client.post(
        "/api/auth/signup",
        json={"email": "alice@example.com", "password": "secret123"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "alice@example.com"
    assert "id" in payload
    assert "password" not in payload
    assert "password_hash" not in payload


def test_signup_stores_bcrypt_hash() -> None:
    client.post(
        "/api/auth/signup",
        json={"email": "alice@example.com", "password": "secret123"},
    )
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "alice@example.com").one()

        assert user.password_hash.startswith("$2b$")
        assert user.password_hash != "secret123"


def test_signup_rejects_password_outside_bcrypt_limits() -> None:
    short_response = client.post(
        "/api/auth/signup",
        json={"email": "alice@example.com", "password": "short"},
    )
    long_response = client.post(
        "/api/auth/signup",
        json={"email": "alice@example.com", "password": "a" * 73},
    )

    assert short_response.status_code == 422
    assert long_response.status_code == 422


def test_signup_duplicate_email_fails() -> None:
    client.post(
        "/api/auth/signup",
        json={"email": "alice@example.com", "password": "secret123"},
    )

    response = client.post(
        "/api/auth/signup",
        json={"email": "alice@example.com", "password": "secret123"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_signup_normalizes_email_before_duplicate_check() -> None:
    client.post(
        "/api/auth/signup",
        json={"email": "alice@example.com", "password": "secret123"},
    )

    response = client.post(
        "/api/auth/signup",
        json={"email": "ALICE@example.com", "password": "secret123"},
    )

    assert response.status_code == 409


def test_login_success_returns_jwt() -> None:
    signup_response = client.post(
        "/api/auth/signup",
        json={"email": "alice@example.com", "password": "secret123"},
    )

    response = client.post(
        "/api/auth/login",
        data={"username": "alice@example.com", "password": "secret123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert data["access_token"]
    claims = jwt.decode(
        data["access_token"],
        JWT_SECRET,
        algorithms=["HS256"],
    )
    assert claims["sub"] == str(signup_response.json()["id"])
    seconds_remaining = claims["exp"] - datetime.now(timezone.utc).timestamp()
    assert 30 * 60 <= seconds_remaining <= 60 * 60
    assert jwt.get_unverified_header(data["access_token"])["alg"] == "HS256"


def test_login_wrong_password_fails() -> None:
    client.post(
        "/api/auth/signup",
        json={"email": "alice@example.com", "password": "secret123"},
    )

    response = client.post(
        "/api/auth/login",
        data={"username": "alice@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_unknown_email_returns_same_error() -> None:
    response = client.post(
        "/api/auth/login",
        data={"username": "unknown@example.com", "password": "secret123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_me_returns_authenticated_user() -> None:
    signup_response = client.post(
        "/api/auth/signup",
        json={"email": "alice@example.com", "password": "secret123"},
    )
    login_response = client.post(
        "/api/auth/login",
        data={"username": "alice@example.com", "password": "secret123"},
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == signup_response.json()["id"]
    assert response.json()["email"] == "alice@example.com"
    assert "password_hash" not in response.json()


def test_me_requires_valid_token() -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_expired_token_is_rejected() -> None:
    expired_token = jwt.encode(
        {"sub": "alice@example.com", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        JWT_SECRET,
        algorithm="HS256",
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"


def test_tampered_token_is_rejected() -> None:
    token = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        os.getenv("JWT_SECRET", "test-secret-value-long-enough-for-hmac"),
        algorithm="HS256",
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}tampered"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_openapi_exposes_oauth2_password_authorization() -> None:
    response = client.get("/openapi.json")
    security_schemes = response.json()["components"]["securitySchemes"]

    assert any(
        scheme["type"] == "oauth2"
        and scheme["flows"]["password"]["tokenUrl"] == "/api/auth/login"
        for scheme in security_schemes.values()
    )

    docs_response = client.get("/docs")
    assert docs_response.status_code == 200
    assert "swagger-ui" in docs_response.text.lower()


def test_delete_my_account_removes_session_and_owned_data() -> None:
    signup = client.post(
        "/api/auth/signup",
        json={"email": "delete@example.com", "password": "secret123"},
    )
    login = client.post(
        "/api/auth/login",
        data={"username": "delete@example.com", "password": "secret123"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    application = client.post(
        "/api/applications",
        headers=headers,
        json={"company": "Delete Co", "role": "Engineer", "jd_text": "Backend"},
    ).json()
    reminder = client.post(
        f"/api/applications/{application['id']}/reminders",
        headers=headers,
        json={"due_at": "2030-01-01T00:00:00Z"},
    )
    assert reminder.status_code == 201
    deletion = client.delete("/api/auth/me", headers=headers)

    assert deletion.status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    with SessionLocal() as db:
        assert db.query(User).filter(User.email == "delete@example.com").count() == 0
        assert db.query(Application).filter(Application.id == application["id"]).count() == 0
        assert db.query(StatusHistory).filter_by(application_id=application["id"]).count() == 0
        assert db.query(Reminder).filter(Reminder.application_id == application["id"]).count() == 0


def test_cors_allows_only_configured_origin() -> None:
    allowed = client.options(
        "/api/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    rejected = client.options(
        "/api/auth/me",
        headers={
            "Origin": "https://not-allowed.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in rejected.headers
