from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Application, Reminder, User
from app.schemas import ReminderCreate, ReminderList, ReminderOut
from app.security import get_current_user

router = APIRouter(tags=["reminders"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def reminder_response(reminder: Reminder, application: Application) -> ReminderOut:
    return ReminderOut(
        id=reminder.id,
        application_id=reminder.application_id,
        due_at=reminder.due_at,
        note=reminder.note,
        done=reminder.done,
        company=application.company,
        role=application.role,
    )


@router.post(
    "/applications/{application_id}/reminders",
    response_model=ReminderOut,
    status_code=status.HTTP_201_CREATED,
)
def create_reminder(
    application_id: int,
    payload: ReminderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderOut:
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == current_user.id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    reminder = Reminder(
        application_id=application.id,
        due_at=payload.due_at,
        note=payload.note,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder_response(reminder, application)


@router.get("/reminders", response_model=ReminderList)
def list_reminders(
    due: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderList:
    query = (
        db.query(Reminder, Application)
        .join(Application, Reminder.application_id == Application.id)
        .filter(Application.user_id == current_user.id)
    )
    if due:
        query = query.filter(Reminder.done.is_(False), Reminder.due_at <= utc_now())

    total = query.with_entities(func.count(Reminder.id)).scalar() or 0
    rows = (
        query.order_by(Reminder.due_at.asc(), Reminder.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return ReminderList(
        items=[reminder_response(reminder, application) for reminder, application in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/reminders/{reminder_id}/done", response_model=ReminderOut)
def mark_reminder_done(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderOut:
    result = (
        db.query(Reminder, Application)
        .join(Application, Reminder.application_id == Application.id)
        .filter(Reminder.id == reminder_id, Application.user_id == current_user.id)
        .first()
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    reminder, application = result
    if not reminder.done:
        reminder.done = True
        db.commit()
        db.refresh(reminder)
    return reminder_response(reminder, application)
