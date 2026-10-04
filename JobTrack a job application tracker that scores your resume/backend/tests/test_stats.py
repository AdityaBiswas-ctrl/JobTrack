from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Application, Reminder, Resume, StatusHistory, User
from app.routers.stats import utc_today
from app.schemas import ApplicationStatus
from scripts.seed_demo_data import DEMO_EMAIL, DEMO_PASSWORD, create_demo_user

client = TestClient(app)
STATS_TODAY = date(2026, 10, 5)


@pytest.fixture(autouse=True)
def reset_database_and_date_override() -> None:
    app.dependency_overrides[utc_today] = lambda: STATS_TODAY
    with SessionLocal() as db:
        db.query(Resume).delete()
        db.query(StatusHistory).delete()
        db.query(Reminder).delete()
        db.query(Application).delete()
        db.query(User).delete()
        db.commit()
    yield
    app.dependency_overrides.pop(utc_today, None)
    with SessionLocal() as db:
        db.query(Resume).delete()
        db.query(StatusHistory).delete()
        db.query(Reminder).delete()
        db.query(Application).delete()
        db.query(User).delete()
        db.commit()


def token_for(email: str, password: str = "secret123") -> str:
    signup = client.post(
        "/api/auth/signup",
        json={"email": email, "password": password},
    )
    assert signup.status_code == 201
    login = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def seed_demo() -> str:
    with SessionLocal() as db:
        create_demo_user(db, STATS_TODAY)
    login = client.post(
        "/api/auth/login",
        data={"username": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def test_seed_data_returns_hand_counted_stats() -> None:
    token = seed_demo()

    response = client.get(
        "/api/stats",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["counts_by_status"] == {
        "wishlist": 1,
        "applied": 1,
        "online_assessment": 0,
        "interview": 1,
        "offer": 1,
        "rejected": 1,
        "withdrawn": 1,
    }
    assert data["response_rate"] == 60.0
    assert data["average_days_to_first_response"] == 3.33
    assert data["median_days_to_first_response"] == 3.0

    weeks = data["applications_per_week"]
    assert len(weeks) == 12
    assert [entry["week_start"] for entry in weeks] == [
        (week_start(STATS_TODAY) - timedelta(weeks=11 - index)).isoformat()
        for index in range(12)
    ]
    expected_week_counts: dict[date, int] = {}
    for days_ago in (20, 13, 6, 5, 2):
        applied_on = STATS_TODAY - timedelta(days=days_ago)
        expected_week_counts[week_start(applied_on)] = (
            expected_week_counts.get(week_start(applied_on), 0) + 1
        )
    assert {
        date.fromisoformat(entry["week_start"]): entry["count"]
        for entry in weeks
    } == {
        week: expected_week_counts.get(week, 0)
        for week in (date.fromisoformat(entry["week_start"]) for entry in weeks)
    }


def test_user_without_applications_gets_zero_buckets_and_null_metrics() -> None:
    token = token_for("empty@example.com")

    response = client.get("/api/stats", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert set(data["counts_by_status"].values()) == {0}
    assert len(data["applications_per_week"]) == 12
    assert all(week["count"] == 0 for week in data["applications_per_week"])
    assert data["response_rate"] is None
    assert data["average_days_to_first_response"] is None
    assert data["median_days_to_first_response"] is None


def test_stats_are_isolated_between_users() -> None:
    token_a = seed_demo()
    token_b = token_for("bob@example.com")

    response_a = client.get("/api/stats", headers={"Authorization": f"Bearer {token_a}"})
    response_b = client.get("/api/stats", headers={"Authorization": f"Bearer {token_b}"})

    assert response_a.json()["counts_by_status"]["rejected"] == 1
    assert set(response_b.json()["counts_by_status"].values()) == {0}
    assert response_b.json()["response_rate"] is None


def test_rejected_is_response_but_withdrawn_and_wishlist_are_not() -> None:
    token = seed_demo()

    stats = client.get("/api/stats", headers={"Authorization": f"Bearer {token}"}).json()

    # Three responded applications out of five non-wishlist applications.
    assert stats["response_rate"] == 60.0
    assert stats["counts_by_status"]["rejected"] == 1
    assert stats["counts_by_status"]["withdrawn"] == 1
    assert stats["counts_by_status"]["wishlist"] == 1


def test_history_counts_an_application_once_and_uses_earliest_response() -> None:
    token = seed_demo()
    with SessionLocal() as db:
        rejected_application = (
            db.query(Application).filter(Application.company == "Contoso").one()
        )
        responses = (
            db.query(StatusHistory)
            .filter(
                StatusHistory.application_id == rejected_application.id,
                StatusHistory.to_status.in_(("online_assessment", "rejected")),
            )
            .order_by(StatusHistory.changed_at)
            .all()
        )
        assert len(responses) == 2
        assert responses[0].to_status == "online_assessment"
        earliest_changed_at = responses[0].changed_at
        if earliest_changed_at.tzinfo is None:
            earliest_changed_at = earliest_changed_at.replace(tzinfo=timezone.utc)
        earliest_delta = earliest_changed_at - datetime.combine(
            rejected_application.applied_on,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        assert earliest_delta.days == 3

    stats = client.get("/api/stats", headers={"Authorization": f"Bearer {token}"}).json()
    assert stats["response_rate"] == 60.0
    assert stats["average_days_to_first_response"] == 3.33


def test_stats_requires_authentication() -> None:
    response = client.get("/api/stats")

    assert response.status_code == 401


def test_status_count_response_has_every_application_status() -> None:
    token = token_for("empty@example.com")

    response = client.get("/api/stats", headers={"Authorization": f"Bearer {token}"})

    assert set(response.json()["counts_by_status"]) == set(ApplicationStatus.__args__)
