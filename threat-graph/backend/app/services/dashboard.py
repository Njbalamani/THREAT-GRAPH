from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.graph.factory import get_graph_store
from app.ml.pipeline import model_status
from app.models.enums import IndicatorType, JobStatus, Severity
from app.models.investigation import Investigation
from app.models.threat import GraphRelationship, Indicator, IngestionJob
from app.schemas.investigation import InvestigationOut
from app.schemas.threat import IndicatorOut, IngestionJobOut


def summary(db: Session) -> dict:
    indicator_count = db.scalar(select(func.count(Indicator.id))) or 0
    type_rows = db.execute(select(Indicator.type, func.count(Indicator.id)).group_by(Indicator.type)).all()
    severity_rows = db.execute(select(Indicator.severity, func.count(Indicator.id)).group_by(Indicator.severity)).all()
    provenance_rows = db.execute(
        select(GraphRelationship.provenance, func.count(GraphRelationship.id)).group_by(GraphRelationship.provenance)
    ).all()
    status_rows = db.execute(select(Investigation.status, func.count(Investigation.id)).group_by(Investigation.status)).all()

    suspicious_ip_count = (
        db.scalar(
            select(func.count(Indicator.id)).where(
                Indicator.type == IndicatorType.IP,
                (Indicator.is_confirmed.is_(True)) | (Indicator.severity.in_([Severity.HIGH, Severity.CRITICAL])),
            )
        )
        or 0
    )
    malicious_domain_count = (
        db.scalar(
            select(func.count(Indicator.id)).where(
                Indicator.type == IndicatorType.DOMAIN,
                (Indicator.is_confirmed.is_(True)) | (Indicator.severity == Severity.CRITICAL),
            )
        )
        or 0
    )

    high_risk = list(
        db.scalars(
            select(Indicator)
            .where(Indicator.severity.in_([Severity.HIGH, Severity.CRITICAL]))
            .order_by(Indicator.confidence.desc(), Indicator.last_seen.desc())
            .limit(10)
        ).all()
    )
    recent_jobs = list(db.scalars(select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(8)).all())
    recent_cases = list(db.scalars(select(Investigation).order_by(Investigation.updated_at.desc()).limit(8)).all())
    running_jobs = db.scalar(select(func.count(IngestionJob.id)).where(IngestionJob.status == JobStatus.RUNNING)) or 0

    return {
        "totals": {
            "indicators": indicator_count,
            "suspicious_ips": suspicious_ip_count,
            "malicious_domains": malicious_domain_count,
            "relationships": db.scalar(select(func.count(GraphRelationship.id))) or 0,
            "investigations": db.scalar(select(func.count(Investigation.id))) or 0,
            "running_ingestion_jobs": running_jobs,
        },
        "indicator_types": {str(key.value): value for key, value in type_rows},
        "severity_distribution": {str(key.value): value for key, value in severity_rows},
        "relationship_provenance": {str(key.value): value for key, value in provenance_rows},
        "investigation_status": {str(key.value): value for key, value in status_rows},
        "graph": get_graph_store().stats(),
        "model": model_status(db),
        "high_risk_indicators": [IndicatorOut.model_validate(item).model_dump(mode="json") for item in high_risk],
        "recent_investigations": [InvestigationOut.model_validate(item).model_dump(mode="json") for item in recent_cases],
        "recent_ingestion_jobs": [IngestionJobOut.model_validate(item).model_dump(mode="json") for item in recent_jobs],
        "disclaimer": "Model predictions are advisory and are not confirmed attacks.",
    }
