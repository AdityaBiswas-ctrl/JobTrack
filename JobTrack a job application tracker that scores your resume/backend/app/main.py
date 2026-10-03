from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.db import Base, engine
from app.routers.applications import router as applications_router
from app.routers.auth import router as auth_router
from app.routers.reminders import router as reminders_router
from app.routers.resumes import router as resumes_router
from app.routers.scoring import router as scoring_router
from app.routers.stats import router as stats_router

app = FastAPI(title="JobTrack API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router, prefix="/api")
app.include_router(applications_router, prefix="/api")
app.include_router(reminders_router, prefix="/api")
app.include_router(resumes_router, prefix="/api")
app.include_router(scoring_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
