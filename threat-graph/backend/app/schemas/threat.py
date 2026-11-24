from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FeedType, IndicatorType, JobStatus, Severity


class IndicatorBase(BaseModel):
    type: IndicatorType
    value: str = Field(min_length=1, max_length=1024)
    severity: Severity = Severity.MEDIUM
    confidence: float = Field(default=0.5, ge=0, le=1)
    source: str = Field(default="manual", max_length=255)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    stix_id: str | None = None
    is_confirmed: bool = False


class IndicatorCreate(IndicatorBase):
    pass


class IndicatorUpdate(BaseModel):
    severity: Severity | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    description: str | None = None
    tags: list[str] | None = None
    is_confirmed: bool | None = None


class IndicatorOut(IndicatorBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    first_seen: datetime
    last_seen: datetime
    raw: dict = Field(default_factory=dict)


class SecurityEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    external_id: str
    event_type: str
    timestamp: datetime
    source_ip: str | None = None
    destination_ip: str | None = None
    domain: str | None = None
    file_hash: str | None = None
    url: str | None = None
    title: str
    description: str | None = None
    severity: Severity
    source: str
    raw: dict = Field(default_factory=dict)


class IngestionJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    file_name: str | None = None
    format: str
    status: JobStatus
    total_records: int
    imported_indicators: int
    imported_events: int
    rejected_records: int
    errors: list[dict] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None = None


class FeedConfigBase(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    feed_type: FeedType
    url: str = Field(min_length=8, max_length=2048)
    collection_id: str | None = None
    auth_header_env: str | None = Field(default=None, max_length=255)
    enabled: bool = False
    poll_interval_minutes: int = Field(default=60, ge=5, le=10080)


class FeedConfigCreate(FeedConfigBase):
    pass


class FeedConfigUpdate(BaseModel):
    description: str | None = None
    url: str | None = Field(default=None, min_length=8, max_length=2048)
    collection_id: str | None = None
    auth_header_env: str | None = Field(default=None, max_length=255)
    enabled: bool | None = None
    poll_interval_minutes: int | None = Field(default=None, ge=5, le=10080)


class FeedConfigOut(FeedConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    last_polled_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    created_at: datetime


class MLModelRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: str
    model_type: str
    metrics: dict
    features: list[str]
    training_samples: int
    label_source: str
    artifact_path: str
    created_at: datetime
