from datetime import date, datetime, timedelta, timezone
from statistics import mean, median
from typing import get_args

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Application, StatusHistory
from app.schemas import ApplicationStatus, StatsOut, WeekCount

RESPONSE_STATUSES = ("online_assessment", "interview", "offer", "rejected")
ALL_STATUSES = get_args(ApplicationStatus)
WEEK_COUNT = 12


def get_user_stats(db: Session, user_id: int, today: date) -> StatsOut:
    counts_by_status = {application_status: 0 for application_status in ALL_STATUSES}
    grouped_status_counts = (
        db.query(Application.status, func.count(Application.id))
        .filter(Application.user_id == user_id)
        .group_by(Application.status)
        .all()
    )
    for application_status, count in grouped_status_counts:
        counts_by_status[application_status] = count

    current_week = today - timedelta(days=today.weekday())
    first_week = current_week - timedelta(weeks=WEEK_COUNT - 1)
    grouped_application_dates = (
        db.query(Application.applied_on, func.count(Application.id))
        .filter(
            Application.user_id == user_id,
            Application.applied_on >= first_week,
            Application.applied_on <= today,
        )
        .group_by(Application.applied_on)
        .all()
    )
    weekly_counts = {first_week + timedelta(weeks=i): 0 for i in range(WEEK_COUNT)}
    for applied_on, count in grouped_application_dates:
        week_start = applied_on - timedelta(days=applied_on.weekday())
        weekly_counts[week_start] += count
    applications_per_week = [
        WeekCount(week_start=week_start, count=count)
        for week_start, count in weekly_counts.items()
    ]

    denominator = (
        db.query(func.count(Application.id))
        .filter(
            Application.user_id == user_id,
            Application.status != "wishlist",
        )
        .scalar()
        or 0
    )
    response_application_count = (
        db.query(func.count(func.distinct(Application.id)))
        .join(StatusHistory, StatusHistory.application_id == Application.id)
        .filter(
            Application.user_id == user_id,
            Application.status != "wishlist",
            StatusHistory.to_status.in_(RESPONSE_STATUSES),
        )
        .scalar()
        or 0
    )
    response_rate = (
        round(response_application_count / denominator * 100, 2)
        if denominator
        else None
    )

    first_responses = (
        db.query(Application.applied_on, func.min(StatusHistory.changed_at))
        .join(StatusHistory, StatusHistory.application_id == Application.id)
        .filter(
            Application.user_id == user_id,
            Application.status != "wishlist",
            Application.applied_on.is_not(None),
            StatusHistory.to_status.in_(RESPONSE_STATUSES),
        )
        .group_by(Application.id, Application.applied_on)
        .all()
    )
    elapsed_days: list[float] = []
    for applied_on, first_response_at in first_responses:
        if first_response_at.tzinfo is None:
            first_response_at = first_response_at.replace(tzinfo=timezone.utc)
        response_date = first_response_at.astimezone(timezone.utc).date()
        elapsed_days.append(float((response_date - applied_on).days))

    return StatsOut(
        counts_by_status=counts_by_status,
        applications_per_week=applications_per_week,
        response_rate=response_rate,
        average_days_to_first_response=round(mean(elapsed_days), 2) if elapsed_days else None,
        median_days_to_first_response=round(median(elapsed_days), 2) if elapsed_days else None,
    )
