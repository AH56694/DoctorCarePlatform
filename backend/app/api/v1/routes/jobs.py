from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.models import JobPosting
from backend.app.db.session import get_db
from backend.app.schemas.jobs import JobPostingCreate, JobPostingRead

router = APIRouter()


@router.post("", response_model=JobPostingRead)
async def create_job(payload: JobPostingCreate, db: Session = Depends(get_db)) -> JobPosting:
    job = JobPosting(**payload.model_dump(), status="published")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[JobPostingRead])
async def list_jobs(db: Session = Depends(get_db)) -> list[JobPosting]:
    return db.query(JobPosting).order_by(JobPosting.created_at.desc()).limit(50).all()
