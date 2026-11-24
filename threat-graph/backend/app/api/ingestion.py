from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_analyst
from app.core.config import settings
from app.core.database import get_db
from app.ingestion.service import ingest_bytes
from app.models.threat import IngestionJob
from app.models.user import User
from app.schemas.threat import IngestionJobOut

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class IngestTextRequest(BaseModel):
    content: str = Field(min_length=2)
    filename: str = Field(default="inline.txt", min_length=1, max_length=255)
    source: str = Field(default="inline", min_length=1, max_length=255)
    format_hint: str | None = None


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    source: str = Form("upload"),
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> dict:
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded file is too large")
    result = ingest_bytes(
        db,
        content,
        filename=file.filename,
        source=source,
        created_by=user.id,
    )
    return result.to_dict()


@router.post("/text")
def ingest_text(
    payload: IngestTextRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> dict:
    content = payload.content.encode("utf-8")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Payload is too large")
    result = ingest_bytes(
        db,
        content,
        filename=payload.filename,
        source=payload.source,
        created_by=user.id,
        format_hint=payload.format_hint,
    )
    return result.to_dict()


@router.get("/jobs", response_model=list[IngestionJobOut])
def list_jobs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[IngestionJobOut]:
    jobs = list(db.scalars(select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit)).all())
    return [IngestionJobOut.model_validate(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=IngestionJobOut)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> IngestionJobOut:
    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return IngestionJobOut.model_validate(job)
