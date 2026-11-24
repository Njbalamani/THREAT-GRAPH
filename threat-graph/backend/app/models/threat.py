from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import IndicatorType, JobStatus, Provenance, Severity
from app.models.user import new_id, utcnow


class Indicator(Base):
    __tablename__ = "indicators"
    __table_args__ = (
        UniqueConstraint("type", "value", name="uq_indicator_type_value"),
        Index("ix_indicators_value", "value"),
        Index("ix_indicators_severity", "severity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[IndicatorType] = mapped_column(Enum(IndicatorType), nullable=False)
    value: Mapped[str] = mapped_column(String(1024), nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), default=Severity.MEDIUM, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    source: Mapped[str] = mapped_column(String(255), default="manual", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    stix_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(default=False, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    raw: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = (
        UniqueConstraint("external_id", "source", name="uq_event_external_source"),
        Index("ix_events_timestamp", "timestamp"),
        Index("ix_events_type", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    destination_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="Security event", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), default=Severity.MEDIUM, nullable=False)
    source: Mapped[str] = mapped_column(String(255), default="import", nullable=False)
    raw: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class GraphRelationship(Base):
    __tablename__ = "graph_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_key",
            "target_key",
            "relation_type",
            "provenance",
            name="uq_graph_relationship",
        ),
        Index("ix_graph_source", "source_key"),
        Index("ix_graph_target", "target_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    target_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provenance: Mapped[Provenance] = mapped_column(Enum(Provenance), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    strength: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(String(255), default="relationship-engine", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    format: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.RUNNING, nullable=False)
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_indicators: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MLModelRun(Base):
    __tablename__ = "ml_model_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    version: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    model_type: Mapped[str] = mapped_column(String(100), default="RandomForestClassifier", nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    features: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    training_samples: Mapped[int] = mapped_column(default=0, nullable=False)
    label_source: Mapped[str] = mapped_column(String(100), default="heuristic", nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
