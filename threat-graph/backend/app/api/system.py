from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_analyst
from app.core.config import settings
from app.core.database import get_db
from app.ingestion.service import ingest_bytes
from app.models.user import User

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ThreatGraph"}


@router.post("/seed-samples")
def seed_samples(
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> dict:
    sample_dir: Path = settings.backend_root / "sample_data"
    files = sorted(path for path in sample_dir.iterdir() if path.is_file()) if sample_dir.exists() else []
    results = []
    for path in files:
        result = ingest_bytes(
            db,
            path.read_bytes(),
            filename=path.name,
            source=f"sample:{path.name}",
            created_by=user.id,
        )
        results.append({"file": path.name, **result.to_dict()})
    return {"seeded_files": len(files), "results": results}
