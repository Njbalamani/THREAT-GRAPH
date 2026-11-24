from pydantic import BaseModel, Field

from app.models.enums import Severity


class ReportRequest(BaseModel):
    title: str = Field(default="ThreatGraph Intelligence Report", min_length=3, max_length=200)
    investigation_id: str | None = None
    indicator_ids: list[str] = Field(default_factory=list)
    include_predictions: bool = True
    minimum_severity: Severity = Severity.LOW
