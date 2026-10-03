from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Resume, User
from app.schemas import ResumeOut
from app.security import get_current_user

MAX_RESUME_BYTES = 2 * 1024 * 1024
MAX_RESUMES_PER_USER = 5

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
def upload_resume(
    file: UploadFile = File(...),
    label: str = Form(min_length=1, max_length=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Resume:
    count = db.query(Resume).filter(Resume.user_id == current_user.id).count()
    if count >= MAX_RESUMES_PER_USER:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resume limit reached")
    label = label.strip()
    if not label:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Label must not be empty")

    file_bytes = file.file.read(MAX_RESUME_BYTES + 1)
    if len(file_bytes) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="PDF must not exceed 2 MB")
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Uploaded file is not a valid PDF")

    filename = file.filename or "resume.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Resume filename must end in .pdf",
        )
    resume = Resume(
        user_id=current_user.id,
        label=label,
        filename=filename[:255],
        file_bytes=file_bytes,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeOut])
def list_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Resume]:
    return (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.uploaded_at.desc(), Resume.id.desc())
        .all()
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    db.delete(resume)
    db.commit()
