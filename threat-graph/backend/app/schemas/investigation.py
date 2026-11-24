from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import InvestigationStatus, Priority, Severity


class InvestigationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str | None = None
    priority: Priority = Priority.MEDIUM


class InvestigationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = None
    status: InvestigationStatus | None = None
    priority: Priority | None = None


class InvestigationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None
    status: InvestigationStatus
    priority: Priority
    created_at: datetime
    updated_at: datetime


class NoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    content: str
    author_id: str | None
    created_at: datetime


class TimelineEventOut(BaseModel):
    id: str
    kind: str
    title: str
    description: str | None
    timestamp: datetime
    severity: Severity | None = None
    source: str | None = None


class InvestigationDetail(BaseModel):
    investigation: InvestigationOut
    indicators: list[dict]
    notes: list[NoteOut]
    timeline: list[TimelineEventOut]
