from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models import Application, Reminder, Resume, Score, StatusHistory, User
from app.routers import scoring as scoring_router
from app.routers.scoring import get_scorer_client
from app.services.scorer_client import ScorerClient

client = TestClient(app)
PDF_BYTES = b"%PDF-1.4\nvalid-looking test upload"


@pytest.fixture(autouse=True)
def reset_database_and_rate_limit() -> None:
    scoring_router._score_attempts.clear()
    with SessionLocal() as db:
        db.query(Score).delete()
        db.query(Resume).delete()
        db.query(StatusHistory).delete()
        db.query(Reminder).delete()
        db.query(Application).delete()
        db.query(User).delete()
        db.commit()
    yield
    app.dependency_overrides.pop(get_scorer_client, None)
    scoring_router._score_attempts.clear()
    with SessionLocal() as db:
        db.query(Score).delete()
        db.query(Resume).delete()
        db.query(StatusHistory).delete()
        db.query(Reminder).delete()
        db.query(Application).delete()
        db.query(User).delete()
        db.commit()


def create_user(email: str) -> str:
    signup = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "secret123"},
    )
    assert signup.status_code == 201
    login = client.post(
        "/api/auth/login",
        data={"username": email, "password": "secret123"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def create_application(token: str, jd_text: str = "Python engineer with SQL skills") -> dict[str, Any]:
    response = client.post(
        "/api/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"company": "Acme", "role": "Engineer", "jd_text": jd_text},
    )
    assert response.status_code == 201
    return response.json()


def upload_resume(token: str, contents: bytes = PDF_BYTES, filename: str = "resume.pdf") -> dict[str, Any]:
    response = client.post(
        "/api/resumes",
        headers={"Authorization": f"Bearer {token}"},
        data={"label": "Main resume"},
        files={"file": (filename, contents, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


def install_scorer(handler: Any) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def record_and_handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(record_and_handle)
    app.dependency_overrides[get_scorer_client] = lambda: ScorerClient(
        "http://mock-scorer",
        timeout_seconds=0.2,
        transport=transport,
    )
    return requests


def success_response(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/score"
    assert b'name="resume_file"' in request.content
    assert b'name="job_description"' in request.content
    return httpx.Response(
        200,
        json={
            "status": "success",
            "filename": "resume.pdf",
            "similarity_score": 81.25,
            "rating": "Excellent Match",
            "matched_keywords": ["python"],
            "missing_keywords": ["sql"],
            "resume_keyword_count": 7,
            "jd_keyword_count": 9,
        },
    )


def score_request(token: str, application_id: int, resume_id: int):
    return client.post(
        f"/api/applications/{application_id}/score",
        headers={"Authorization": f"Bearer {token}"},
        json={"resume_id": resume_id},
    )


def test_upload_accepts_pdf_and_lists_only_owned_resumes() -> None:
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    resume = upload_resume(token_a)
    upload_resume(token_b, filename="bob-resume.pdf")

    listed = client.get("/api/resumes", headers={"Authorization": f"Bearer {token_a}"})

    assert resume["filename"] == "resume.pdf"
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == resume["id"]
    assert "file_bytes" not in listed.json()[0]


def test_upload_rejects_spoofed_pdf_and_file_over_two_megabytes() -> None:
    token = create_user("alice@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    not_pdf = client.post(
        "/api/resumes",
        headers=headers,
        data={"label": "Bad file"},
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    valid_content_wrong_extension = client.post(
        "/api/resumes",
        headers=headers,
        data={"label": "Wrong extension"},
        files={"file": ("resume.txt", PDF_BYTES, "application/pdf")},
    )
    oversized = client.post(
        "/api/resumes",
        headers=headers,
        data={"label": "Large file"},
        files={"file": ("large.pdf", b"%PDF-" + b"x" * (2 * 1024 * 1024), "application/pdf")},
    )

    assert not_pdf.status_code == 422
    assert valid_content_wrong_extension.status_code == 422
    assert oversized.status_code == 413


def test_resume_limit_is_five_and_upload_requires_auth() -> None:
    token = create_user("alice@example.com")
    unauthenticated = client.post(
        "/api/resumes",
        data={"label": "Main resume"},
        files={"file": ("resume.pdf", PDF_BYTES, "application/pdf")},
    )
    assert unauthenticated.status_code == 401

    for index in range(5):
        response = client.post(
            "/api/resumes",
            headers={"Authorization": f"Bearer {token}"},
            data={"label": f"Resume {index}"},
            files={"file": (f"{index}.pdf", PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == 201

    too_many = client.post(
        "/api/resumes",
        headers={"Authorization": f"Bearer {token}"},
        data={"label": "Sixth resume"},
        files={"file": ("sixth.pdf", PDF_BYTES, "application/pdf")},
    )
    assert too_many.status_code == 409


def test_resume_get_and_delete_are_owner_scoped() -> None:
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    resume = upload_resume(token_a)

    other_list = client.get("/api/resumes", headers={"Authorization": f"Bearer {token_b}"})
    other_delete = client.delete(
        f"/api/resumes/{resume['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    owner_delete = client.delete(
        f"/api/resumes/{resume['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    get_after_delete = client.get("/api/resumes", headers={"Authorization": f"Bearer {token_a}"})

    assert other_list.json() == []
    assert other_delete.status_code == 404
    assert owner_delete.status_code == 204
    assert get_after_delete.json() == []


def test_successful_score_is_stored_and_returned_with_latency() -> None:
    requests = install_scorer(success_response)
    token = create_user("alice@example.com")
    application = create_application(token)
    resume = upload_resume(token)

    response = score_request(token, application["id"], resume["id"])

    assert response.status_code == 200
    result = response.json()
    assert result["match_score"] == 81.25
    assert result["missing_keywords"] == ["sql"]
    assert result["scorer_status"] == "ok"
    assert result["latency_ms"] >= 0
    assert result["cache_hit"] is False
    assert len(requests) == 1
    stored = client.get(
        f"/api/applications/{application['id']}/scores",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert stored.status_code == 200
    assert len(stored.json()) == 1


def test_cache_uses_normalized_job_description_and_calls_scorer_once() -> None:
    requests = install_scorer(success_response)
    token = create_user("alice@example.com")
    application = create_application(token, "  PYTHON   ENGINEER with SQL skills ")
    resume = upload_resume(token)

    first = score_request(token, application["id"], resume["id"])
    with SessionLocal() as db:
        db.execute(
            text("UPDATE applications SET jd_text = :jd WHERE id = :id"),
            {"jd": "python engineer WITH sql skills", "id": application["id"]},
        )
        db.commit()
    second = score_request(token, application["id"], resume["id"])

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["cache_hit"] is True
    assert second.json()["latency_ms"] == 0
    assert len(requests) == 1


def test_empty_job_description_returns_422_without_calling_scorer() -> None:
    requests = install_scorer(success_response)
    token = create_user("alice@example.com")
    application = create_application(token, " \n\t ")
    resume = upload_resume(token)

    response = score_request(token, application["id"], resume["id"])

    assert response.status_code == 422
    assert requests == []
    assert client.get("/api/applications", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_other_user_gets_404_for_resume_or_application_while_scoring() -> None:
    requests = install_scorer(success_response)
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    application_a = create_application(token_a)
    resume_a = upload_resume(token_a)
    application_b = create_application(token_b)
    resume_b = upload_resume(token_b)

    other_application = score_request(token_b, application_a["id"], resume_b["id"])
    other_resume = score_request(token_b, application_b["id"], resume_a["id"])

    assert other_application.status_code == 404
    assert other_resume.status_code == 404
    assert requests == []


def test_timeout_stores_failure_does_not_cache_and_other_endpoints_work() -> None:
    attempts = 0

    def timeout_then_success(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise httpx.ReadTimeout("scorer timeout", request=request)
        return success_response(request)

    install_scorer(timeout_then_success)
    token = create_user("alice@example.com")
    application = create_application(token)
    resume = upload_resume(token)

    failed = score_request(token, application["id"], resume["id"])
    with SessionLocal() as db:
        failure = db.query(Score).filter(Score.application_id == application["id"]).one()
        assert failure.scorer_status == "timeout"
        assert failure.match_score is None
    applications = client.get("/api/applications", headers={"Authorization": f"Bearer {token}"})
    succeeded = score_request(token, application["id"], resume["id"])

    assert failed.status_code == 503
    assert "may be waking up" in failed.json()["detail"]
    assert applications.status_code == 200
    assert succeeded.status_code == 200
    assert attempts == 3


def test_server_error_then_success_retries_once() -> None:
    attempts = 0

    def fail_once(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={"detail": "temporary"})
        return success_response(request)

    install_scorer(fail_once)
    token = create_user("alice@example.com")
    application = create_application(token)
    resume = upload_resume(token)

    response = score_request(token, application["id"], resume["id"])

    assert response.status_code == 200
    assert attempts == 2


def test_two_server_errors_store_error_after_exactly_two_calls() -> None:
    requests = install_scorer(lambda request: httpx.Response(500, json={"detail": "down"}))
    token = create_user("alice@example.com")
    application = create_application(token)
    resume = upload_resume(token)

    response = score_request(token, application["id"], resume["id"])

    assert response.status_code == 503
    assert len(requests) == 2
    with SessionLocal() as db:
        failure = db.query(Score).filter(Score.application_id == application["id"]).one()
        assert failure.scorer_status == "error"
        assert failure.match_score is None


def test_client_error_is_not_retried_and_stores_error() -> None:
    requests = install_scorer(lambda request: httpx.Response(400, json={"detail": "bad request"}))
    token = create_user("alice@example.com")
    application = create_application(token)
    resume = upload_resume(token)

    response = score_request(token, application["id"], resume["id"])

    assert response.status_code == 503
    assert len(requests) == 1
    with SessionLocal() as db:
        failure = db.query(Score).filter(Score.application_id == application["id"]).one()
        assert failure.scorer_status == "error"


def test_malformed_scorer_payload_returns_clear_error_row() -> None:
    requests = install_scorer(lambda request: httpx.Response(200, json={"status": "success"}))
    token = create_user("alice@example.com")
    application = create_application(token)
    resume = upload_resume(token)

    response = score_request(token, application["id"], resume["id"])

    assert response.status_code == 503
    assert "invalid response" in response.json()["detail"]
    assert len(requests) == 1
    with SessionLocal() as db:
        failure = db.query(Score).filter(Score.application_id == application["id"]).one()
        assert failure.scorer_status == "error"
        assert failure.match_score is None
        assert failure.missing_keywords_json is None


def test_eleventh_uncached_score_request_is_rate_limited() -> None:
    requests = install_scorer(success_response)
    token = create_user("alice@example.com")
    application = create_application(token, "Role 0")
    resume = upload_resume(token)
    response_codes: list[int] = []

    for index in range(11):
        with SessionLocal() as db:
            db.execute(
                text("UPDATE applications SET jd_text = :jd WHERE id = :id"),
                {"jd": f"unique job description {index}", "id": application["id"]},
            )
            db.commit()
        response_codes.append(score_request(token, application["id"], resume["id"]).status_code)

    assert response_codes == [200] * 10 + [429]
    assert len(requests) == 10


def test_score_history_is_owner_scoped() -> None:
    install_scorer(success_response)
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    application = create_application(token_a)
    resume = upload_resume(token_a)
    score_request(token_a, application["id"], resume["id"])

    response = client.get(
        f"/api/applications/{application['id']}/scores",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 404


def test_score_client_validates_contract_fields() -> None:
    invalid_payload = {
        "status": "success",
        "filename": "resume.pdf",
        "similarity_score": 140,
        "rating": "Good",
        "matched_keywords": [],
        "missing_keywords": [],
        "resume_keyword_count": 0,
        "jd_keyword_count": 0,
    }
    install_scorer(lambda request: httpx.Response(200, json=invalid_payload))
    token = create_user("alice@example.com")
    application = create_application(token)
    resume = upload_resume(token)

    response = score_request(token, application["id"], resume["id"])

    assert response.status_code == 503
    assert "invalid response" in response.json()["detail"]


def test_score_timestamps_are_utc_aware() -> None:
    install_scorer(success_response)
    token = create_user("alice@example.com")
    application = create_application(token)
    resume = upload_resume(token)

    response = score_request(token, application["id"], resume["id"])

    created_at = datetime.fromisoformat(response.json()["created_at"])
    assert created_at.tzinfo is not None
    assert created_at.utcoffset() == timedelta(0)
