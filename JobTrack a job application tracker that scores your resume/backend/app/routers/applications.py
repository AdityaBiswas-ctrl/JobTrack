from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Application, StatusHistory, User
from app.schemas import (
    ApplicationCreate,
    ApplicationList,
    ApplicationOut,
    ApplicationStatus,
    ApplicationUpdate,
    StatusChange,
    StatusHistoryOut,
)
from app.security import get_current_user

router = APIRouter(prefix="/applications", tags=["applications"])


def find_application(db: Session, application_id: int, user_id: int) -> Application:
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == user_id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Application:
    application_data = payload.model_dump()
    if application_data["job_url"] is not None:
        application_data["job_url"] = str(application_data["job_url"])
    application = Application(user_id=current_user.id, **application_data)
    db.add(application)
    db.flush()
    db.add(
        StatusHistory(
            application_id=application.id,
            from_status="",
            to_status="wishlist",
        )
    )
    db.commit()
    db.refresh(application)
    return application


@router.patch("/{application_id}/status", response_model=ApplicationOut)
def update_application_status(
    application_id: int,
    payload: StatusChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Application:
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if application.status == payload.status:
        return application

    previous_status = application.status
    application.status = payload.status
    application.updated_at = datetime.now(timezone.utc)
    db.add(
        StatusHistory(
            application_id=application.id,
            from_status=previous_status,
            to_status=payload.status,
            note=payload.note,
        )
    )
    db.commit()
    db.refresh(application)
    return application


@router.get("/{application_id}/history", response_model=list[StatusHistoryOut])
def list_application_history(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StatusHistory]:
    find_application(db, application_id, current_user.id)
    return (
        db.query(StatusHistory)
        .join(Application, StatusHistory.application_id == Application.id)
        .filter(
            StatusHistory.application_id == application_id,
            Application.user_id == current_user.id,
        )
        .order_by(StatusHistory.changed_at.asc(), StatusHistory.id.asc())
        .all()
    )


@router.get("", response_model=ApplicationList)
def list_applications(
    status_filter: ApplicationStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationList:
    query = db.query(Application).filter(Application.user_id == current_user.id)
    if status_filter is not None:
        query = query.filter(Application.status == status_filter)
    if q and q.strip():
        escaped_query = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_pattern = f"%{escaped_query}%"
        query = query.filter(
            Application.company.ilike(search_pattern, escape="\\")
            | Application.role.ilike(search_pattern, escape="\\")
        )

    total = query.with_entities(func.count(Application.id)).scalar() or 0
    items = (
        query.order_by(Application.created_at.desc(), Application.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return ApplicationList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Application:
    return find_application(db, application_id, current_user.id)


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Application:
    application = find_application(db, application_id, current_user.id)
    update_data = payload.model_dump(exclude_unset=True)
    if "job_url" in update_data and update_data["job_url"] is not None:
        update_data["job_url"] = str(update_data["job_url"])
    for field, value in update_data.items():
        setattr(application, field, value)
    application.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(application)
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    application = find_application(db, application_id, current_user.id)
    db.delete(application)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
