import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Application, Reminder, Resume, StatusHistory, User

client = TestClient(app)
PDF_BYTES = b"%PDF-1.4\nvalid-looking test upload"


@pytest.fixture(autouse=True)
def reset_database() -> None:
    with SessionLocal() as db:
        db.query(Resume).delete()
        db.query(StatusHistory).delete()
        db.query(Reminder).delete()
        db.query(Application).delete()
        db.query(User).delete()
        db.commit()
    yield
    with SessionLocal() as db:
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


def upload_resume(
    token: str,
    contents: bytes = PDF_BYTES,
    filename: str = "resume.pdf",
) -> dict:
    response = client.post(
        "/api/resumes",
        headers={"Authorization": f"Bearer {token}"},
        data={"label": "Main resume"},
        files={"file": (filename, contents, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


def test_resume_api_keeps_upload_management_without_scoring_routes() -> None:
    paths = app.openapi()["paths"]

    assert "/api/resumes" in paths
    assert "/api/resumes/{resume_id}" in paths
    assert not any("/score" in path or "/scores" in path for path in paths)


def test_upload_accepts_pdf_and_lists_only_owned_resumes() -> None:
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    resume = upload_resume(token_a)
    upload_resume(token_b, filename="bob-resume.pdf")

    listed = client.get(
        "/api/resumes",
        headers={"Authorization": f"Bearer {token_a}"},
    )

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


def test_resume_list_and_delete_are_owner_scoped() -> None:
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    resume = upload_resume(token_a)

    other_list = client.get(
        "/api/resumes",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    other_delete = client.delete(
        f"/api/resumes/{resume['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    owner_delete = client.delete(
        f"/api/resumes/{resume['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    get_after_delete = client.get(
        "/api/resumes",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert other_list.json() == []
    assert other_delete.status_code == 404
    assert owner_delete.status_code == 204
    assert get_after_delete.json() == []
