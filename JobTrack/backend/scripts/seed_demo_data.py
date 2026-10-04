import argparse
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import Application, StatusHistory, User
from app.security import hash_password

DEMO_EMAIL = "demo@jobtrack.local"
DEMO_PASSWORD = "demo-password"
DEMO_APPLICATIONS = [
    ("Northwind", "Backend Engineer", "interview", 20, [(1, "applied"), (5, "interview")]),
    (
        "Contoso",
        "Python Developer",
        "rejected",
        13,
        [(1, "applied"), (3, "online_assessment"), (5, "rejected")],
    ),
    ("Fabrikam", "API Engineer", "offer", 6, [(0, "applied"), (2, "offer")]),
    ("Adventure Works", "Platform Engineer", "withdrawn", 5, [(0, "applied"), (3, "withdrawn")]),
    ("Tailspin", "Software Engineer", "applied", 2, [(0, "applied")]),
    ("Woodgrove", "Developer", "wishlist", None, []),
]


def add_history(
    db: Session,
    application: Application,
    changed_at: datetime,
    from_status: str,
    to_status: str,
) -> None:
    db.add(
        StatusHistory(
            application_id=application.id,
            from_status=from_status,
            to_status=to_status,
            changed_at=changed_at,
        )
    )


def create_demo_user(db: Session, today: date, application_count: int = 6) -> User:
    if application_count < 1:
        raise ValueError("application_count must be at least 1")

    existing_user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if existing_user is not None:
        db.delete(existing_user)
        db.flush()

    user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
    db.add(user)
    db.flush()

    if application_count == len(DEMO_APPLICATIONS):
        rows = DEMO_APPLICATIONS
    else:
        rows = []
        statuses = (
            "wishlist",
            "applied",
            "online_assessment",
            "interview",
            "offer",
            "rejected",
            "withdrawn",
        )
        response_statuses = {"online_assessment", "interview", "offer", "rejected"}
        for index in range(application_count):
            current_status = statuses[index % len(statuses)]
            applied_days_ago = None if current_status == "wishlist" else 10 + index % 70
            events = [] if current_status == "wishlist" else [(0, "applied")]
            if current_status in response_statuses:
                events.append((2 + index % 5, current_status))
            elif current_status == "withdrawn":
                events.append((3, "withdrawn"))
            rows.append(
                (
                    f"Demo Company {index + 1}",
                    f"Demo Role {index + 1}",
                    current_status,
                    applied_days_ago,
                    events,
                )
            )

    for index, (company, role, current_status, applied_days_ago, events) in enumerate(rows):
        applied_on = (
            today - timedelta(days=applied_days_ago)
            if applied_days_ago is not None
            else None
        )
        history_day = applied_on or today
        initial_time = datetime.combine(history_day, time(hour=9), tzinfo=timezone.utc)
        application = Application(
            user_id=user.id,
            company=company,
            role=role,
            status=current_status,
            applied_on=applied_on,
            created_at=initial_time,
            updated_at=initial_time,
        )
        db.add(application)
        db.flush()
        add_history(db, application, initial_time, "", "wishlist")

        previous_status = "wishlist"
        for days_after_applied, next_status in events:
            changed_at = initial_time + timedelta(days=days_after_applied, hours=1)
            add_history(db, application, changed_at, previous_status, next_status)
            previous_status = next_status

    db.commit()
    return user


def main() -> None:
    parser = argparse.ArgumentParser(description="Create local JobTrack demo data.")
    parser.add_argument(
        "--count",
        type=int,
        default=len(DEMO_APPLICATIONS),
        help="Number of demo applications to create (default: 6).",
    )
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        create_demo_user(db, date.today(), args.count)
    print(f"Created {args.count} demo applications for {DEMO_EMAIL}.")


if __name__ == "__main__":
    main()
