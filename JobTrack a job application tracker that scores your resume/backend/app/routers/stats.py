from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import StatsOut
from app.security import get_current_user
from app.services.stats_service import get_user_stats

router = APIRouter(tags=["stats"])


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


@router.get("/stats", response_model=StatsOut)
def get_stats(
    today: date = Depends(utc_today),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StatsOut:
    return get_user_stats(db, current_user.id, today)
