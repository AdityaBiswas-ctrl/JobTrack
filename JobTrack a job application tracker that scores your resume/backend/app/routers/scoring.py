import hashlib
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import SCORER_TIMEOUT_SECONDS, SCORER_URL
from app.db import get_db
from app.models import Application, Resume, Score, User
from app.schemas import ScoreOut, ScoreRequest
from app.security import get_current_user
from app.services.scorer_client import ScorerClient, ScorerError, ScorerTimeout

router = APIRouter(prefix="/applications", tags=["scoring"])

MAX_SCORES_PER_HOUR = 10
RATE_LIMIT_WINDOW_SECONDS = 60 * 60
_score_attempts: dict[int, list[float]] = defaultdict(list)
_clock: Callable[[], float] = time.time
_rate_limit_lock = Lock()


def get_scorer_client() -> ScorerClient:
    return ScorerClient(SCORER_URL, SCORER_TIMEOUT_SECONDS)


def normalize_job_description(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def score_output(score: Score, cache_hit: bool = False) -> ScoreOut:
    return ScoreOut(
        id=score.id,
        application_id=score.application_id,
        resume_id=score.resume_id,
        jd_hash=score.jd_hash,
        match_score=score.match_score,
        missing_keywords=score.missing_keywords_json,
        scorer_status=score.scorer_status,
        latency_ms=score.latency_ms,
        created_at=score.created_at,
        cache_hit=cache_hit,
    )


def cached_score(db: Session, resume_id: int, jd_hash: str) -> Score | None:
    return (
        db.query(Score)
        .filter(
            Score.resume_id == resume_id,
            Score.jd_hash == jd_hash,
            Score.scorer_status == "ok",
        )
        .order_by(Score.created_at.desc(), Score.id.desc())
        .first()
    )


def enforce_rate_limit(user_id: int) -> None:
    with _rate_limit_lock:
        now = _clock()
        attempts = [
            attempt
            for attempt in _score_attempts[user_id]
            if now - attempt < RATE_LIMIT_WINDOW_SECONDS
        ]
        if len(attempts) >= MAX_SCORES_PER_HOUR:
            _score_attempts[user_id] = attempts
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Scoring limit reached; try again later",
            )
        attempts.append(now)
        _score_attempts[user_id] = attempts


@router.post("/{application_id}/score", response_model=ScoreOut)
def score_application(
    application_id: int,
    payload: ScoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scorer: ScorerClient = Depends(get_scorer_client),
) -> ScoreOut:
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == current_user.id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    resume = (
        db.query(Resume)
        .filter(Resume.id == payload.resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    normalized_jd = normalize_job_description(application.jd_text or "")
    if not normalized_jd:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Application job description is empty",
        )
    jd_hash = hashlib.sha256(normalized_jd.encode("utf-8")).hexdigest()

    cached = cached_score(db, resume.id, jd_hash)
    if cached is not None:
        cache_row = Score(
            application_id=application.id,
            resume_id=resume.id,
            jd_hash=jd_hash,
            match_score=cached.match_score,
            missing_keywords_json=cached.missing_keywords_json,
            scorer_status="ok",
            latency_ms=0,
        )
        db.add(cache_row)
        db.commit()
        db.refresh(cache_row)
        return score_output(cache_row, cache_hit=True)

    enforce_rate_limit(current_user.id)
    started_at = time.perf_counter()
    try:
        scorer_result = scorer.score(
            filename=resume.filename,
            pdf_bytes=resume.file_bytes,
            job_description=application.jd_text or "",
        )
    except ScorerTimeout as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        failure = Score(
            application_id=application.id,
            resume_id=resume.id,
            jd_hash=jd_hash,
            match_score=None,
            missing_keywords_json=None,
            scorer_status="timeout",
            latency_ms=latency_ms,
        )
        db.add(failure)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scorer timed out; it may be waking up. Please try again later.",
        ) from exc
    except ScorerError as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        failure = Score(
            application_id=application.id,
            resume_id=resume.id,
            jd_hash=jd_hash,
            match_score=None,
            missing_keywords_json=None,
            scorer_status="error",
            latency_ms=latency_ms,
        )
        db.add(failure)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Scorer unavailable: {exc}",
        ) from exc

    latency_ms = int((time.perf_counter() - started_at) * 1000)
    score = Score(
        application_id=application.id,
        resume_id=resume.id,
        jd_hash=jd_hash,
        match_score=scorer_result.similarity_score,
        missing_keywords_json=scorer_result.missing_keywords,
        scorer_status="ok",
        latency_ms=latency_ms,
    )
    db.add(score)
    db.commit()
    db.refresh(score)
    return score_output(score)


@router.get("/{application_id}/scores", response_model=list[ScoreOut])
def list_application_scores(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ScoreOut]:
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.user_id == current_user.id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    scores = (
        db.query(Score)
        .filter(Score.application_id == application.id)
        .order_by(Score.created_at.desc(), Score.id.desc())
        .all()
    )
    return [score_output(score) for score in scores]
