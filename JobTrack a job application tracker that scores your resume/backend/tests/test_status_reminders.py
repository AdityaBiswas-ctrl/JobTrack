from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app.db import SessionLocal
from app.main import app
from app.models import Application, Reminder, StatusHistory, User
from app.routers import reminders as reminders_router

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


def create_application(token: str, company: str = "Acme") -> dict[str, Any]:
    response = client.post(
        "/api/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"company": company, "role": "Engineer"},
    )
    assert response.status_code == 201
    return response.json()


def create_reminder(token: str, application_id: int, due_at: datetime) -> dict[str, Any]:
    response = client.post(
        f"/api/applications/{application_id}/reminders",
        headers={"Authorization": f"Bearer {token}"},
        json={"due_at": due_at.isoformat(), "note": "Follow up"},
    )
    assert response.status_code == 201
    return response.json()


def test_status_change_updates_application_and_writes_one_history_row() -> None:
    token = create_user("alice@example.com")
    application = create_application(token)

    response = client.patch(
        f"/api/applications/{application['id']}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "applied", "note": "Submitted application"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    with SessionLocal() as db:
        history = (
            db.query(StatusHistory)
            .filter(StatusHistory.application_id == application["id"])
            .order_by(StatusHistory.id)
            .all()
        )
        assert len(history) == 2
        assert history[0].from_status == ""
        assert history[0].to_status == "wishlist"
        assert history[1].from_status == "wishlist"
        assert history[1].to_status == "applied"
        assert history[1].note == "Submitted application"


def test_same_status_is_idempotent_and_invalid_status_is_rejected() -> None:
    token = create_user("alice@example.com")
    application = create_application(token)
    headers = {"Authorization": f"Bearer {token}"}

    unchanged = client.patch(
        f"/api/applications/{application['id']}/status",
        headers=headers,
        json={"status": "wishlist"},
    )
    invalid = client.patch(
        f"/api/applications/{application['id']}/status",
        headers=headers,
        json={"status": "unknown"},
    )

    assert unchanged.status_code == 200
    assert invalid.status_code == 422
    with SessionLocal() as db:
        count = (
            db.query(StatusHistory)
            .filter(StatusHistory.application_id == application["id"])
            .count()
        )
        assert count == 1


def test_status_and_history_changes_rollback_together_on_flush_failure() -> None:
    token = create_user("alice@example.com")
    application = create_application(token)
    statements: list[str] = []

    def record_statement(connection: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool) -> None:
        statements.append(statement.upper())

    with SessionLocal() as db:
        db.execute(
            text(
                "CREATE TRIGGER reject_applied_history BEFORE INSERT ON status_history "
                "WHEN NEW.to_status = 'applied' "
                "BEGIN SELECT RAISE(ABORT, 'simulated history write failure'); END"
            )
        )
        db.commit()

    event.listen(SessionLocal.kw["bind"], "before_cursor_execute", record_statement)
    try:
        response = TestClient(app, raise_server_exceptions=False).patch(
            f"/api/applications/{application['id']}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "applied"},
        )
    finally:
        event.remove(SessionLocal.kw["bind"], "before_cursor_execute", record_statement)
        with SessionLocal() as db:
            db.execute(text("DROP TRIGGER reject_applied_history"))
            db.commit()

    assert response.status_code == 500
    update_position = next(i for i, statement in enumerate(statements) if statement.startswith("UPDATE APPLICATIONS"))
    history_insert_position = next(
        i for i, statement in enumerate(statements) if statement.startswith("INSERT INTO STATUS_HISTORY")
    )
    assert update_position < history_insert_position
    with SessionLocal() as db:
        stored_application = db.get(Application, application["id"])
        history_count = (
            db.query(StatusHistory)
            .filter(StatusHistory.application_id == application["id"])
            .count()
        )
        assert stored_application is not None
        assert stored_application.status == "wishlist"
        assert history_count == 1


def test_history_is_ordered_and_includes_creation_record() -> None:
    token = create_user("alice@example.com")
    application = create_application(token)
    headers = {"Authorization": f"Bearer {token}"}
    for new_status in ("applied", "interview"):
        response = client.patch(
            f"/api/applications/{application['id']}/status",
            headers=headers,
            json={"status": new_status},
        )
        assert response.status_code == 200

    history = client.get(
        f"/api/applications/{application['id']}/history",
        headers=headers,
    )

    assert history.status_code == 200
    entries = history.json()
    assert [entry["to_status"] for entry in entries] == ["wishlist", "applied", "interview"]
    changed_at = [datetime.fromisoformat(entry["changed_at"]) for entry in entries]
    assert changed_at == sorted(changed_at)
    assert all(timestamp.tzinfo is not None for timestamp in changed_at)


def test_status_history_and_status_change_are_owned_resources() -> None:
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    application = create_application(token_a)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    history = client.get(
        f"/api/applications/{application['id']}/history",
        headers=headers_b,
    )
    status_change = client.patch(
        f"/api/applications/{application['id']}/status",
        headers=headers_b,
        json={"status": "applied"},
    )

    assert history.status_code == 404
    assert status_change.status_code == 404
    owner_view = client.get(
        f"/api/applications/{application['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert owner_view.json()["status"] == "wishlist"


def test_create_reminder_requires_auth_and_timezone_aware_datetime() -> None:
    token = create_user("alice@example.com")
    application = create_application(token)
    url = f"/api/applications/{application['id']}/reminders"

    no_auth = client.post(url, json={"due_at": "2026-10-03T12:00:00"})
    naive_time = client.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"due_at": "2026-10-03T12:00:00"},
    )

    assert no_auth.status_code == 401
    assert naive_time.status_code == 422


def test_reminder_due_time_is_normalized_to_utc() -> None:
    token = create_user("alice@example.com")
    application = create_application(token)
    local_due_at = datetime(2026, 10, 4, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    reminder = create_reminder(token, application["id"], local_due_at)

    normalized_due_at = datetime.fromisoformat(reminder["due_at"])
    assert normalized_due_at.utcoffset() == timedelta(0)
    assert normalized_due_at.hour == 6
    assert normalized_due_at.minute == 30


def test_create_reminder_and_due_view_only_returns_callers_past_due_open_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(reminders_router, "utc_now", lambda: now)
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    application_a = create_application(token_a, "Alice Co")
    application_b = create_application(token_b, "Bob Co")
    past = create_reminder(token_a, application_a["id"], now - timedelta(minutes=1))
    create_reminder(token_a, application_a["id"], now + timedelta(minutes=1))
    done_reminder = create_reminder(token_a, application_a["id"], now - timedelta(minutes=2))
    create_reminder(token_b, application_b["id"], now - timedelta(minutes=3))
    client.patch(
        f"/api/reminders/{done_reminder['id']}/done",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    due = client.get(
        "/api/reminders?due=true",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert due.status_code == 200
    assert due.json()["total"] == 1
    item = due.json()["items"][0]
    assert item["id"] == past["id"]
    assert item["company"] == "Alice Co"
    assert item["role"] == "Engineer"
    assert datetime.fromisoformat(item["due_at"]).utcoffset() == timedelta(0)


def test_all_reminders_support_pagination_for_current_user() -> None:
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    application_a = create_application(token_a, "Alice Co")
    application_b = create_application(token_b, "Bob Co")
    now = datetime.now(timezone.utc)
    for offset in range(3):
        create_reminder(token_a, application_a["id"], now + timedelta(minutes=offset))
    create_reminder(token_b, application_b["id"], now)

    response = client.get(
        "/api/reminders?limit=2&offset=1",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert response.json()["limit"] == 2
    assert response.json()["offset"] == 1
    assert all(item["company"] == "Alice Co" for item in response.json()["items"])


def test_other_user_cannot_create_or_mark_reminder_done() -> None:
    token_a = create_user("alice@example.com")
    token_b = create_user("bob@example.com")
    application = create_application(token_a)
    reminder = create_reminder(
        token_a,
        application["id"],
        datetime.now(timezone.utc) + timedelta(days=1),
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    create_for_other = client.post(
        f"/api/applications/{application['id']}/reminders",
        headers=headers_b,
        json={"due_at": datetime.now(timezone.utc).isoformat()},
    )
    list_for_other = client.get("/api/reminders", headers=headers_b)
    mark_other_done = client.patch(
        f"/api/reminders/{reminder['id']}/done",
        headers=headers_b,
    )

    assert create_for_other.status_code == 404
    assert list_for_other.status_code == 200
    assert list_for_other.json()["total"] == 0
    assert mark_other_done.status_code == 404


def test_mark_done_is_idempotent_and_removes_reminder_from_due_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(reminders_router, "utc_now", lambda: now)
    token = create_user("alice@example.com")
    application = create_application(token)
    reminder = create_reminder(token, application["id"], now - timedelta(minutes=1))
    headers = {"Authorization": f"Bearer {token}"}
    url = f"/api/reminders/{reminder['id']}/done"

    first = client.patch(url, headers=headers)
    second = client.patch(url, headers=headers)
    due = client.get("/api/reminders?due=true", headers=headers)

    assert first.status_code == 200
    assert first.json()["done"] is True
    assert second.status_code == 200
    assert second.json()["done"] is True
    assert due.json()["total"] == 0


def test_deleting_application_cascades_history_and_reminders() -> None:
    token = create_user("alice@example.com")
    application = create_application(token)
    create_reminder(
        token,
        application["id"],
        datetime.now(timezone.utc) + timedelta(days=1),
    )

    deleted = client.delete(
        f"/api/applications/{application['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert deleted.status_code == 204
    with SessionLocal() as db:
        assert db.query(StatusHistory).filter_by(application_id=application["id"]).count() == 0
        assert db.query(Reminder).filter_by(application_id=application["id"]).count() == 0
