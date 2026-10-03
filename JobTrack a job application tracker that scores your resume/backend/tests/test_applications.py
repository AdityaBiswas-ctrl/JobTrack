from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Application, Reminder, StatusHistory, User

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db() -> None:
    with SessionLocal() as db:
        db.query(StatusHistory).delete()
        db.query(Reminder).delete()
        db.query(Application).delete()
        db.query(User).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(StatusHistory).delete()
        db.query(Reminder).delete()
        db.query(Application).delete()
        db.query(User).delete()
        db.commit()


def create_user(email: str) -> str:
    signup_response = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "secret123"},
    )
    assert signup_response.status_code == 201
    login_response = client.post(
        "/api/auth/login",
        data={"username": email, "password": "secret123"},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def create_application(token: str, company: str, role: str = "Engineer") -> dict[str, Any]:
    response = client.post(
        "/api/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"company": company, "role": role},
    )
    assert response.status_code == 201
    return response.json()


def test_create_application_defaults_to_wishlist() -> None:
    token = create_user("alice@example.com")

    response = client.post(
        "/api/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "company": "  Acme  ",
            "role": " Engineer ",
            "job_url": "https://jobs.example.com/123",
            "location": "Remote",
            "source": "Company site",
            "applied_on": "2026-10-01",
            "notes": "Follow up",
            "jd_text": "Python developer",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["company"] == "Acme"
    assert data["role"] == "Engineer"
    assert data["status"] == "wishlist"
    assert data["user_id"] > 0
    history_response = client.get(
        f"/api/applications/{data['id']}/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history_response.status_code == 200
    assert len(history_response.json()) == 1
    assert history_response.json()[0]["from_status"] == ""
    assert history_response.json()[0]["to_status"] == "wishlist"


def test_create_application_requires_authentication() -> None:
    response = client.post(
        "/api/applications",
        json={"company": "Acme", "role": "Engineer"},
    )

    assert response.status_code == 401


def test_list_applications_requires_authentication() -> None:
    response = client.get("/api/applications")

    assert response.status_code == 401


def test_create_application_rejects_invalid_url_and_oversized_description() -> None:
    token = create_user("alice@example.com")

    invalid_url = client.post(
        "/api/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"company": "Acme", "role": "Engineer", "job_url": "not-a-url"},
    )
    oversized_description = client.post(
        "/api/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"company": "Acme", "role": "Engineer", "jd_text": "x" * 20_001},
    )

    assert invalid_url.status_code == 422
    assert oversized_description.status_code == 422


def test_create_application_rejects_empty_company_and_unknown_status() -> None:
    token = create_user("alice@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    empty_company = client.post(
        "/api/applications",
        headers=headers,
        json={"company": "  ", "role": "Engineer"},
    )
    with_status = client.post(
        "/api/applications",
        headers=headers,
        json={"company": "Acme", "role": "Engineer", "status": "offer"},
    )

    assert empty_company.status_code == 422
    assert with_status.status_code == 422


def test_list_only_returns_current_users_applications() -> None:
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    application_a = create_application(token_a, "Alice Co")
    create_application(token_b, "Bob Co")

    response = client.get(
        "/api/applications",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [application_a["id"]]


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_other_user_cannot_read_change_or_delete_application(method: str) -> None:
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    application = create_application(token_a, "Alice Co")
    headers = {"Authorization": f"Bearer {token_b}"}
    url = f"/api/applications/{application['id']}"

    if method == "get":
        response = client.get(url, headers=headers)
    elif method == "patch":
        response = client.patch(url, headers=headers, json={"notes": "stolen"})
    else:
        response = client.delete(url, headers=headers)

    assert response.status_code == 404
    owner_response = client.get(
        url,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert owner_response.status_code == 200
    assert owner_response.json()["notes"] is None


def test_pagination_uses_total_and_stable_order() -> None:
    token = create_user("alice@example.com")
    created = [create_application(token, f"Company {i}") for i in range(4)]
    same_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with SessionLocal() as db:
        db.query(Application).update({Application.created_at: same_time})
        db.commit()

    headers = {"Authorization": f"Bearer {token}"}
    first_page = client.get("/api/applications?limit=2&offset=0", headers=headers)
    second_page = client.get("/api/applications?limit=2&offset=2", headers=headers)

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 4
    assert first_page.json()["limit"] == 2
    assert first_page.json()["offset"] == 0
    expected_ids = sorted((item["id"] for item in created), reverse=True)
    assert [item["id"] for item in first_page.json()["items"]] == expected_ids[:2]
    assert [item["id"] for item in second_page.json()["items"]] == expected_ids[2:]


def test_list_filters_status_and_search_with_literal_wildcards() -> None:
    token = create_user("alice@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    special_application = create_application(token, "Acme_100%")
    role_match = create_application(token, "Other Co", role="Acme Engineer")
    create_application(token, "Different Co")

    with SessionLocal() as db:
        db.query(Application).filter(Application.id == role_match["id"]).update(
            {Application.status: "applied"}
        )
        db.commit()

    filtered = client.get(
        "/api/applications?status=applied&q=Acme",
        headers=headers,
    )
    literal_percent = client.get("/api/applications?q=%25", headers=headers)

    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [role_match["id"]]
    assert filtered.json()["total"] == 1
    assert [item["id"] for item in literal_percent.json()["items"]] == [special_application["id"]]


def test_invalid_status_filter_returns_422() -> None:
    token = create_user("alice@example.com")

    response = client.get(
        "/api/applications?status=not-a-status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_application_indexes_cover_user_status_and_applied_date() -> None:
    index_columns = {
        tuple(column.name for column in index.columns)
        for index in Application.__table__.indexes
    }

    assert ("user_id", "status") in index_columns
    assert ("user_id", "applied_on") in index_columns


def test_patch_is_partial_updates_timestamp_and_rejects_status() -> None:
    token = create_user("alice@example.com")
    application = create_application(token, "Acme")
    headers = {"Authorization": f"Bearer {token}"}
    with SessionLocal() as db:
        stored = db.query(Application).filter(Application.id == application["id"]).one()
        initial_updated_at = stored.updated_at

    response = client.patch(
        f"/api/applications/{application['id']}",
        headers=headers,
        json={"notes": "new note"},
    )
    forbidden_status = client.patch(
        f"/api/applications/{application['id']}",
        headers=headers,
        json={"status": "applied"},
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "new note"
    assert response.json()["company"] == "Acme"
    assert response.json()["status"] == "wishlist"
    assert response.json()["updated_at"] >= initial_updated_at.isoformat()
    assert forbidden_status.status_code == 422


def test_delete_returns_no_content_then_get_returns_404() -> None:
    token = create_user("alice@example.com")
    application = create_application(token, "Acme")
    headers = {"Authorization": f"Bearer {token}"}

    delete_response = client.delete(
        f"/api/applications/{application['id']}",
        headers=headers,
    )
    get_response = client.get(
        f"/api/applications/{application['id']}",
        headers=headers,
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert get_response.status_code == 404
