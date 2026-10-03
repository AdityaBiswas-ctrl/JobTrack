from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

ApplicationStatus = Literal[
    "wishlist",
    "applied",
    "online_assessment",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
]


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        return password


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ApplicationCreate(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=120)
    job_url: HttpUrl | None = Field(default=None, max_length=2048)
    location: str | None = Field(default=None, max_length=120)
    source: str | None = Field(default=None, max_length=80)
    applied_on: date | None = None
    notes: str | None = None
    jd_text: str | None = Field(default=None, max_length=20_000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("company", "role")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be empty")
        return value


class ApplicationUpdate(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=120)
    role: str | None = Field(default=None, min_length=1, max_length=120)
    job_url: HttpUrl | None = Field(default=None, max_length=2048)
    location: str | None = Field(default=None, max_length=120)
    source: str | None = Field(default=None, max_length=80)
    applied_on: date | None = None
    notes: str | None = None
    jd_text: str | None = Field(default=None, max_length=20_000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("company", "role")
    @classmethod
    def strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("This field must not be null")
        value = value.strip()
        if not value:
            raise ValueError("This field must not be empty")
        return value


class ApplicationOut(BaseModel):
    id: int
    user_id: int
    company: str
    role: str
    job_url: str | None
    location: str | None
    source: str | None
    status: ApplicationStatus
    applied_on: date | None
    notes: str | None
    jd_text: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationList(BaseModel):
    items: list[ApplicationOut]
    total: int
    limit: int
    offset: int


class StatusChange(BaseModel):
    status: ApplicationStatus
    note: str | None = Field(default=None, max_length=2_000)

    model_config = ConfigDict(extra="forbid")


class StatusHistoryOut(BaseModel):
    id: int
    application_id: int
    from_status: str
    to_status: ApplicationStatus
    changed_at: datetime
    note: str | None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("changed_at", mode="before")
    @classmethod
    def stored_timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ReminderCreate(BaseModel):
    due_at: datetime
    note: str | None = Field(default=None, max_length=2_000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("due_at")
    @classmethod
    def require_timezone_and_normalize_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("due_at must include a timezone")
        return value.astimezone(timezone.utc)


class ReminderOut(BaseModel):
    id: int
    application_id: int
    due_at: datetime
    note: str | None
    done: bool
    company: str
    role: str

    model_config = ConfigDict(from_attributes=True)

    @field_validator("due_at", mode="before")
    @classmethod
    def stored_timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ReminderList(BaseModel):
    items: list[ReminderOut]
    total: int
    limit: int
    offset: int


class ResumeOut(BaseModel):
    id: int
    user_id: int
    label: str
    filename: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("uploaded_at", mode="before")
    @classmethod
    def stored_timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ScoreRequest(BaseModel):
    resume_id: int

    model_config = ConfigDict(extra="forbid")


class ScoreOut(BaseModel):
    id: int
    application_id: int
    resume_id: int
    jd_hash: str
    match_score: float | None
    missing_keywords: list[str] | None
    scorer_status: Literal["ok", "timeout", "error"]
    latency_ms: int
    created_at: datetime
    cache_hit: bool = False

    @field_validator("created_at", mode="before")
    @classmethod
    def stored_timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class WeekCount(BaseModel):
    week_start: date
    count: int


class StatsOut(BaseModel):
    counts_by_status: dict[str, int]
    applications_per_week: list[WeekCount]
    response_rate: float | None
    average_days_to_first_response: float | None
    median_days_to_first_response: float | None
