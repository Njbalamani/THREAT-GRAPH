from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ValidationError
from app.graph.relationships import build_relationships, sync_indicator_nodes
from app.ingestion.parsers import NormalizedRecord, normalize_record, parse_content
from app.models.enums import IndicatorType, JobStatus, Severity
from app.models.threat import Indicator, IngestionJob, SecurityEvent

SEVERITY_RANK = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


@dataclass
class IngestionResult:
    job_id: str
    status: str
    format: str
    total_records: int
    imported_indicators: int
    imported_events: int
    rejected_records: int
    errors: list[dict[str, Any]] = field(default_factory=list)
    relationships: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "format": self.format,
            "total_records": self.total_records,
            "imported_indicators": self.imported_indicators,
            "imported_events": self.imported_events,
            "rejected_records": self.rejected_records,
            "errors": self.errors,
            "relationships": self.relationships,
        }


def _as_enum(value: Any) -> IndicatorType | None:
    if isinstance(value, IndicatorType):
        return value
    try:
        return IndicatorType(str(value).lower())
    except ValueError:
        return None


def _merge_tags(existing: list[str], incoming: list[str]) -> list[str]:
    merged: list[str] = []
    for tag in [*existing, *incoming]:
        if tag and tag not in merged:
            merged.append(tag)
    return merged


def _upsert_indicator(db: Session, payload: dict[str, Any]) -> tuple[Indicator | None, bool, str | None]:
    indicator_type = _as_enum(payload.get("type"))
    value = str(payload.get("value") or "").strip().lower()
    if not indicator_type or not value:
        return None, False, "Indicator type or value is invalid"

    existing = db.scalar(select(Indicator).where(Indicator.type == indicator_type, Indicator.value == value))
    incoming_severity = payload.get("severity", Severity.MEDIUM)
    if not isinstance(incoming_severity, Severity):
        incoming_severity = Severity(str(incoming_severity).lower())

    if existing:
        if SEVERITY_RANK.get(incoming_severity, 1) > SEVERITY_RANK.get(existing.severity, 1):
            existing.severity = incoming_severity
        existing.confidence = max(existing.confidence, float(payload.get("confidence") or 0.5))
        existing.last_seen = datetime.now(UTC).replace(tzinfo=None)
        existing.tags = _merge_tags(existing.tags or [], list(payload.get("tags") or []))
        existing.is_confirmed = bool(existing.is_confirmed or payload.get("is_confirmed"))
        if payload.get("description") and not existing.description:
            existing.description = str(payload["description"])
        if payload.get("stix_id") and not existing.stix_id:
            existing.stix_id = str(payload["stix_id"])
        raw = dict(existing.raw or {})
        if payload.get("raw"):
            raw.update(payload["raw"])
        existing.raw = raw
        return existing, False, None

    indicator = Indicator(
        type=indicator_type,
        value=value,
        severity=incoming_severity,
        confidence=float(payload.get("confidence") or 0.5),
        source=str(payload.get("source") or "import"),
        description=payload.get("description"),
        tags=list(payload.get("tags") or []),
        stix_id=payload.get("stix_id"),
        is_confirmed=bool(payload.get("is_confirmed")),
        raw=dict(payload.get("raw") or {}),
    )
    db.add(indicator)
    return indicator, True, None


def _event_from_record(record: NormalizedRecord, source: str) -> SecurityEvent:
    return SecurityEvent(
        external_id=record.external_id,
        event_type=record.event_type,
        timestamp=record.timestamp,
        source_ip=record.source_ip,
        destination_ip=record.destination_ip,
        domain=record.domain,
        file_hash=record.file_hash,
        url=record.url,
        title=record.title,
        description=record.description,
        severity=record.severity,
        source=source,
        raw=record.raw,
    )


def ingest_bytes(
    db: Session,
    content: bytes,
    *,
    filename: str | None = None,
    source: str = "upload",
    created_by: str | None = None,
    format_hint: str | None = None,
) -> IngestionResult:
    if len(content) > settings.max_upload_bytes:
        raise ValidationError(f"Upload exceeds {settings.max_upload_mb} MB limit")

    parsed = parse_content(content, filename)
    if format_hint:
        parsed.format = format_hint

    job = IngestionJob(
        source=source,
        file_name=filename,
        format=parsed.format,
        status=JobStatus.RUNNING,
        created_by=created_by,
    )
    db.add(job)
    db.commit()

    errors = list(parsed.errors)
    touched: list[Indicator] = []
    created_event_ids: list[str] = []
    total = len(parsed.records) + len(parsed.indicators)
    created_indicators = 0

    try:
        for raw_record in parsed.records:
            try:
                normalized = normalize_record(raw_record, source)
                if not any([normalized.source_ip, normalized.destination_ip, normalized.domain, normalized.file_hash, normalized.url]):
                    errors.append({"message": "Record contained no usable indicators", "record": raw_record})
                    continue
                for payload in normalized.indicators:
                    indicator, created, error = _upsert_indicator(db, payload)
                    if error:
                        errors.append({"message": error, "record": raw_record})
                        continue
                    if indicator:
                        touched.append(indicator)
                        created_indicators += int(created)
                existing = db.scalar(
                    select(SecurityEvent).where(
                        SecurityEvent.external_id == normalized.external_id,
                        SecurityEvent.source == source,
                    )
                )
                if existing:
                    continue
                event = _event_from_record(normalized, source)
                db.add(event)
                db.flush()
                created_event_ids.append(event.id)
            except Exception as exc:
                errors.append({"message": str(exc), "record": raw_record})

        for payload in parsed.indicators:
            try:
                indicator, created, error = _upsert_indicator(db, payload)
                if error:
                    errors.append({"message": error})
                    continue
                if indicator:
                    touched.append(indicator)
                    created_indicators += int(created)
            except Exception as exc:
                errors.append({"message": str(exc), "indicator": payload})

        db.commit()

        if created_event_ids:
            relationships = build_relationships(db, event_ids=created_event_ids)
        else:
            relationships = {
                "events_processed": 0,
                "nodes_upserted": sync_indicator_nodes(db, touched),
                "edges_upserted": 0,
                "relationships_created": 0,
                "observed_edges": 0,
                "inferred_edges": 0,
                "backend": "sync",
            }

        job.status = JobStatus.COMPLETED
        job.total_records = total
        job.imported_indicators = created_indicators
        job.imported_events = len(created_event_ids)
        job.rejected_records = len(errors)
        job.errors = errors[:100]
        job.completed_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()

        return IngestionResult(
            job_id=job.id,
            status=job.status.value,
            format=parsed.format,
            total_records=total,
            imported_indicators=created_indicators,
            imported_events=len(created_event_ids),
            rejected_records=len(errors),
            errors=errors[:100],
            relationships=relationships,
        )
    except Exception as exc:
        db.rollback()
        job.status = JobStatus.FAILED
        job.total_records = total
        job.errors = [*errors[:100], {"message": str(exc)}]
        job.completed_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
        raise
