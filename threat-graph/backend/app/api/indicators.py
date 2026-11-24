from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_analyst
from app.core.database import get_db
from app.graph.relationships import sync_indicator_nodes
from app.models.enums import IndicatorType, Severity, UserRole
from app.models.threat import Indicator
from app.models.user import User
from app.schemas.threat import IndicatorCreate, IndicatorOut, IndicatorUpdate

router = APIRouter(prefix="/indicators", tags=["indicators"])


def _get_indicator(db: Session, indicator_id: str) -> Indicator:
    indicator = db.get(Indicator, indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicator not found")
    return indicator


@router.get("", response_model=list[IndicatorOut])
def list_indicators(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    indicator_type: IndicatorType | None = None,
    severity: Severity | None = None,
    search: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[IndicatorOut]:
    stmt = select(Indicator)
    if indicator_type:
        stmt = stmt.where(Indicator.type == indicator_type)
    if severity:
        stmt = stmt.where(Indicator.severity == severity)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(Indicator.value.ilike(pattern), Indicator.description.ilike(pattern)))
    indicators = list(db.scalars(stmt.order_by(Indicator.last_seen.desc()).offset(offset).limit(limit)).all())
    return [IndicatorOut.model_validate(indicator) for indicator in indicators]


@router.get("/{indicator_id}", response_model=IndicatorOut)
def get_indicator(
    indicator_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> IndicatorOut:
    return IndicatorOut.model_validate(_get_indicator(db, indicator_id))


@router.post("", response_model=IndicatorOut, status_code=status.HTTP_201_CREATED)
def create_indicator(
    payload: IndicatorCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> IndicatorOut:
    value = payload.value.strip().lower()
    existing = db.scalar(select(Indicator).where(Indicator.type == payload.type, Indicator.value == value))
    if existing:
        raise HTTPException(status_code=409, detail="Indicator already exists")
    indicator = Indicator(
        type=payload.type,
        value=value,
        severity=payload.severity,
        confidence=payload.confidence,
        source=payload.source,
        description=payload.description,
        tags=payload.tags,
        stix_id=payload.stix_id,
        is_confirmed=payload.is_confirmed,
        raw={"created_by": user.id},
    )
    db.add(indicator)
    db.commit()
    db.refresh(indicator)
    sync_indicator_nodes(db, [indicator])
    return IndicatorOut.model_validate(indicator)


@router.patch("/{indicator_id}", response_model=IndicatorOut)
def update_indicator(
    indicator_id: str,
    payload: IndicatorUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst),
) -> IndicatorOut:
    indicator = _get_indicator(db, indicator_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "value" and value:
            value = value.strip().lower()
        setattr(indicator, key, value)
    db.commit()
    db.refresh(indicator)
    sync_indicator_nodes(db, [indicator])
    return IndicatorOut.model_validate(indicator)


@router.delete("/{indicator_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_indicator(
    indicator_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators may delete indicators")
    indicator = _get_indicator(db, indicator_id)
    db.delete(indicator)
    db.commit()
