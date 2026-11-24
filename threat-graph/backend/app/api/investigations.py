from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_analyst
from app.core.database import get_db
from app.models.enums import IndicatorType
from app.models.investigation import (
    Investigation,
    InvestigationNote,
    investigation_events,
    investigation_indicators,
)
from app.models.threat import Indicator, SecurityEvent
from app.models.user import User
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationDetail,
    InvestigationOut,
    InvestigationUpdate,
    NoteCreate,
    NoteOut,
    TimelineEventOut,
)
from app.schemas.threat import IndicatorOut

router = APIRouter(prefix="/investigations", tags=["investigations"])


def _get_case(db: Session, case_id: str) -> Investigation:
    case = db.get(Investigation, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return case


def _case_indicators(db: Session, case_id: str) -> list[Indicator]:
    return list(
        db.scalars(
            select(Indicator)
            .join(investigation_indicators, investigation_indicators.c.indicator_id == Indicator.id)
            .where(investigation_indicators.c.investigation_id == case_id)
            .order_by(Indicator.severity.desc(), Indicator.value)
        ).all()
    )


def _derived_timeline(db: Session, indicators: list[Indicator]) -> list[SecurityEvent]:
    if not indicators:
        return []
    conditions = []
    for indicator in indicators:
        value = indicator.value.lower()
        if indicator.type == IndicatorType.IP:
            conditions.extend([SecurityEvent.source_ip == value, SecurityEvent.destination_ip == value])
        elif indicator.type == IndicatorType.DOMAIN:
            conditions.append(SecurityEvent.domain == value)
        elif indicator.type == IndicatorType.HASH:
            conditions.append(SecurityEvent.file_hash == value)
        elif indicator.type == IndicatorType.URL:
            conditions.append(SecurityEvent.url == value)
    if not conditions:
        return []
    return list(db.scalars(select(SecurityEvent).where(or_(*conditions)).order_by(SecurityEvent.timestamp)).all())


def _detail(db: Session, case: Investigation) -> InvestigationDetail:
    indicators = _case_indicators(db, case.id)
    notes = list(
        db.scalars(
            select(InvestigationNote).where(InvestigationNote.investigation_id == case.id).order_by(InvestigationNote.created_at)
        ).all()
    )
    events = _derived_timeline(db, indicators)
    timeline: list[TimelineEventOut] = []
    for event in events:
        timeline.append(
            TimelineEventOut(
                id=event.id,
                kind="event",
                title=event.title,
                description=event.description,
                timestamp=event.timestamp,
                severity=event.severity,
                source=event.source,
            )
        )
    for note in notes:
        timeline.append(
            TimelineEventOut(
                id=note.id,
                kind="note",
                title="Analyst note",
                description=note.content,
                timestamp=note.created_at,
            )
        )
    timeline.sort(key=lambda item: item.timestamp)
    return InvestigationDetail(
        investigation=InvestigationOut.model_validate(case),
        indicators=[IndicatorOut.model_validate(indicator).model_dump(mode="json") for indicator in indicators],
        notes=[NoteOut.model_validate(note) for note in notes],
        timeline=timeline,
    )


@router.get("", response_model=list[InvestigationOut])
def list_investigations(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[InvestigationOut]:
    cases = list(db.scalars(select(Investigation).order_by(Investigation.updated_at.desc())).all())
    return [InvestigationOut.model_validate(case) for case in cases]


@router.post("", response_model=InvestigationDetail, status_code=status.HTTP_201_CREATED)
def create_investigation(
    payload: InvestigationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> InvestigationDetail:
    case = Investigation(
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        created_by=user.id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return _detail(db, case)


@router.get("/{case_id}", response_model=InvestigationDetail)
def get_investigation(
    case_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> InvestigationDetail:
    return _detail(db, _get_case(db, case_id))


@router.patch("/{case_id}", response_model=InvestigationOut)
def update_investigation(
    case_id: str,
    payload: InvestigationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst),
) -> InvestigationOut:
    case = _get_case(db, case_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, key, value)
    case.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(case)
    return InvestigationOut.model_validate(case)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investigation(
    case_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst),
) -> None:
    case = _get_case(db, case_id)
    db.execute(delete(investigation_indicators).where(investigation_indicators.c.investigation_id == case_id))
    db.execute(delete(investigation_events).where(investigation_events.c.investigation_id == case_id))
    db.delete(case)
    db.commit()


@router.post("/{case_id}/indicators/{indicator_id}", response_model=InvestigationDetail)
def associate_indicator(
    case_id: str,
    indicator_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> InvestigationDetail:
    case = _get_case(db, case_id)
    indicator = db.get(Indicator, indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicator not found")
    existing = db.execute(
        select(investigation_indicators).where(
            investigation_indicators.c.investigation_id == case_id,
            investigation_indicators.c.indicator_id == indicator_id,
        )
    ).first()
    if not existing:
        db.execute(
            investigation_indicators.insert().values(
                investigation_id=case_id,
                indicator_id=indicator_id,
                added_by=user.id,
            )
        )
        case.updated_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
    return _detail(db, case)


@router.post("/{case_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def add_note(
    case_id: str,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> NoteOut:
    _get_case(db, case_id)
    note = InvestigationNote(
        investigation_id=case_id,
        author_id=user.id,
        content=payload.content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteOut.model_validate(note)


@router.get("/{case_id}/timeline", response_model=list[TimelineEventOut])
def case_timeline(
    case_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[TimelineEventOut]:
    return _detail(db, _get_case(db, case_id)).timeline
