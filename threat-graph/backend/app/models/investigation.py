from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import InvestigationStatus, Priority
from app.models.user import new_id, utcnow

investigation_indicators = Table(
    "investigation_indicators",
    Base.metadata,
    Column("investigation_id", String(36), ForeignKey("investigations.id"), primary_key=True),
    Column("indicator_id", String(36), ForeignKey("indicators.id"), primary_key=True),
    Column("added_by", String(36), ForeignKey("users.id"), nullable=True),
    Column("added_at", DateTime, default=utcnow, nullable=False),
)

investigation_events = Table(
    "investigation_events",
    Base.metadata,
    Column("investigation_id", String(36), ForeignKey("investigations.id"), primary_key=True),
    Column("event_id", String(36), ForeignKey("security_events.id"), primary_key=True),
    Column("added_at", DateTime, default=utcnow, nullable=False),
)


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[InvestigationStatus] = mapped_column(Enum(InvestigationStatus), default=InvestigationStatus.OPEN, nullable=False)
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.MEDIUM, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class InvestigationNote(Base):
    __tablename__ = "investigation_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
