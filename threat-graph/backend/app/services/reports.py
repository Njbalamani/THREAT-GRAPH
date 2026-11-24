from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.graph.factory import get_graph_store
from app.ml.pipeline import predict
from app.models.enums import IndicatorType, Severity
from app.models.investigation import Investigation, InvestigationNote, investigation_indicators
from app.models.threat import GraphRelationship, Indicator, SecurityEvent
from app.schemas.report import ReportRequest

SEVERITY_RANK = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


def _indicators(db: Session, request: ReportRequest) -> list[Indicator]:
    stmt = select(Indicator)
    if request.indicator_ids:
        stmt = stmt.where(Indicator.id.in_(request.indicator_ids))
    minimum = SEVERITY_RANK.get(request.minimum_severity, 0)
    indicators = [
        indicator
        for indicator in db.scalars(stmt.order_by(Indicator.severity.desc(), Indicator.value)).all()
        if SEVERITY_RANK.get(indicator.severity, 0) >= minimum
    ]
    return indicators


def _relationships(db: Session, indicators: list[Indicator]) -> list[GraphRelationship]:
    keys = {f"indicator:{indicator.id}" for indicator in indicators}
    stmt = select(GraphRelationship).order_by(GraphRelationship.created_at.desc()).limit(500)
    relationships = list(db.scalars(stmt).all())
    if not keys:
        return relationships
    return [relationship for relationship in relationships if relationship.source_key in keys or relationship.target_key in keys]


def _investigation_data(db: Session, case_id: str | None) -> tuple[Investigation | None, list[dict], list[dict]]:
    if not case_id:
        return None, [], []
    case = db.get(Investigation, case_id)
    if not case:
        return None, [], []
    indicators = list(
        db.scalars(
            select(Indicator)
            .join(investigation_indicators, investigation_indicators.c.indicator_id == Indicator.id)
            .where(investigation_indicators.c.investigation_id == case_id)
        ).all()
    )
    values = [(indicator.type, indicator.value.lower()) for indicator in indicators]
    events: list[SecurityEvent] = []
    if values:
        candidates = list(db.scalars(select(SecurityEvent).order_by(SecurityEvent.timestamp)).all())
        for event in candidates:
            matched = False
            for indicator_type, value in values:
                if indicator_type == IndicatorType.IP and value in {
                    str(event.source_ip or "").lower(),
                    str(event.destination_ip or "").lower(),
                }:
                    matched = True
                elif indicator_type == IndicatorType.DOMAIN and value == str(event.domain or "").lower():
                    matched = True
                elif indicator_type == IndicatorType.HASH and value == str(event.file_hash or "").lower():
                    matched = True
                elif indicator_type == IndicatorType.URL and value == str(event.url or "").lower():
                    matched = True
                if matched:
                    break
            if matched:
                events.append(event)
    notes = list(
        db.scalars(
            select(InvestigationNote).where(InvestigationNote.investigation_id == case_id).order_by(InvestigationNote.created_at)
        ).all()
    )
    timeline = [
        {
            "kind": "event",
            "timestamp": event.timestamp.isoformat(),
            "title": event.title,
            "description": event.description,
        }
        for event in events
    ]
    timeline.extend(
        {
            "kind": "note",
            "timestamp": note.created_at.isoformat(),
            "title": "Analyst note",
            "description": note.content,
        }
        for note in notes
    )
    timeline.sort(key=lambda item: item["timestamp"])
    return case, indicators, timeline


def build_report_data(db: Session, request: ReportRequest) -> dict:
    indicators = _indicators(db, request)
    relationships = _relationships(db, indicators)
    case, case_indicators, timeline = _investigation_data(db, request.investigation_id)
    predictions = []
    if request.include_predictions:
        predictions = [item for item in predict(db, get_graph_store()) if item["indicator_id"] in {i.id for i in indicators}]
    return {
        "title": request.title,
        "generated_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "indicators": [
            {
                "id": item.id,
                "type": item.type.value,
                "value": item.value,
                "severity": item.severity.value,
                "confidence": item.confidence,
                "source": item.source,
                "is_confirmed": item.is_confirmed,
                "tags": item.tags,
            }
            for item in indicators
        ],
        "relationships": [
            {
                "source": item.source_key,
                "target": item.target_key,
                "relationship": item.relation_type,
                "provenance": item.provenance.value,
                "confidence": item.confidence,
                "strength": item.strength,
                "evidence": item.evidence,
            }
            for item in relationships
        ],
        "investigation": {
            "id": case.id,
            "title": case.title,
            "status": case.status.value,
            "priority": case.priority.value,
        }
        if case
        else None,
        "investigation_indicators": [item.value for item in case_indicators],
        "timeline": timeline,
        "predictions": predictions,
        "disclaimer": "Predictions are advisory model outputs and are not confirmed cyber attacks.",
    }


def _table(data: list[list[str]], widths: list[float]) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10243d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f4f7fb"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#a8b6c8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def generate_pdf(db: Session, request: ReportRequest) -> bytes:
    data = build_report_data(db, request)
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=data["title"],
        author="ThreatGraph",
    )
    styles = getSampleStyleSheet()
    heading = ParagraphStyle(
        "ThreatGraphHeading",
        parent=styles["Heading1"],
        textColor=colors.HexColor("#10243d"),
        alignment=TA_LEFT,
    )
    body = ParagraphStyle(
        "ThreatGraphBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
    )
    warning = ParagraphStyle(
        "ThreatGraphWarning",
        parent=body,
        textColor=colors.HexColor("#9c2b2b"),
        fontName="Helvetica-Bold",
    )

    story = [
        Paragraph(escape(data["title"]), heading),
        Paragraph(f"Generated: {escape(data['generated_at'])}", body),
        Paragraph("ThreatGraph AI-Powered Cyber Attack Relationship Mapping and Prediction System", body),
        Spacer(1, 8 * mm),
        Paragraph(f"Total indicators: {len(data['indicators'])}", body),
        Paragraph(f"Graph relationships: {len(data['relationships'])}", body),
        Paragraph(
            f"Investigation: {escape(data['investigation']['title']) if data['investigation'] else 'Not specified'}",
            body,
        ),
        Spacer(1, 5 * mm),
        Paragraph("Indicators", styles["Heading2"]),
    ]

    indicator_rows = [["Type", "Value", "Severity", "Confidence", "Source"]]
    for item in data["indicators"][:80]:
        indicator_rows.append(
            [
                escape(item["type"]),
                escape(item["value"][:70]),
                escape(item["severity"]),
                f"{item['confidence']:.2f}",
                escape(item["source"][:40]),
            ]
        )
    story.append(_table(indicator_rows, [25 * mm, 75 * mm, 25 * mm, 25 * mm, 34 * mm]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Graph Relationships", styles["Heading2"]))
    relationship_rows = [["Source", "Target", "Relationship", "Provenance", "Confidence"]]
    for item in data["relationships"][:60]:
        relationship_rows.append(
            [
                escape(item["source"][:35]),
                escape(item["target"][:35]),
                escape(item["relationship"]),
                escape(item["provenance"]),
                f"{item['confidence']:.2f}",
            ]
        )
    story.append(_table(relationship_rows, [38 * mm, 38 * mm, 38 * mm, 28 * mm, 22 * mm]))
    story.append(PageBreak())
    story.append(Paragraph("Investigation Timeline", styles["Heading2"]))
    timeline_rows = [["Timestamp", "Kind", "Title", "Details"]]
    for item in data["timeline"][:80]:
        timeline_rows.append(
            [
                escape(item["timestamp"]),
                escape(item["kind"]),
                escape(item["title"][:50]),
                escape(str(item.get("description") or "")[:120]),
            ]
        )
    story.append(_table(timeline_rows, [35 * mm, 18 * mm, 45 * mm, 80 * mm]))

    if data["predictions"]:
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("Model Predictions", styles["Heading2"]))
        prediction_rows = [["Indicator", "Probability", "Risk", "Model Version"]]
        for item in data["predictions"][:50]:
            prediction_rows.append(
                [
                    escape(item["value"][:70]),
                    f"{item['probability']:.2f}",
                    escape(item["risk_level"]),
                    escape(item["model_version"]),
                ]
            )
        story.append(_table(prediction_rows, [75 * mm, 25 * mm, 25 * mm, 50 * mm]))

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Observed relationships are directly extracted from events; inferred relationships are model-derived.", body))
    story.append(Paragraph(escape(data["disclaimer"]), warning))
    document.build(story)
    return buffer.getvalue()


def indicators_csv(db: Session) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "type", "value", "severity", "confidence", "source", "is_confirmed", "tags"])
    for item in db.scalars(select(Indicator).order_by(Indicator.value)).all():
        writer.writerow(
            [
                item.id,
                item.type.value,
                item.value,
                item.severity.value,
                item.confidence,
                item.source,
                item.is_confirmed,
                "|".join(item.tags or []),
            ]
        )
    return output.getvalue().encode("utf-8")


def relationships_csv(db: Session) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "source_key", "target_key", "relationship", "provenance", "confidence", "strength", "evidence"])
    for item in db.scalars(select(GraphRelationship).order_by(GraphRelationship.created_at)).all():
        writer.writerow(
            [
                item.id,
                item.source_key,
                item.target_key,
                item.relation_type,
                item.provenance.value,
                item.confidence,
                item.strength,
                json.dumps(item.evidence, default=str),
            ]
        )
    return output.getvalue().encode("utf-8")


def graph_json() -> bytes:
    store = get_graph_store()
    nodes, edges = store.get_snapshot(limit=5000)
    payload = {
        "backend": store.backend_name,
        "nodes": [
            {
                "key": node.key,
                "id": node.id,
                "type": node.type,
                "label": node.label,
                "properties": node.properties,
            }
            for node in nodes
        ],
        "edges": [
            {
                "key": edge.key,
                "source": edge.source,
                "target": edge.target,
                "relationship": edge.relationship,
                "provenance": edge.provenance,
                "confidence": edge.confidence,
                "strength": edge.strength,
                "properties": edge.properties,
            }
            for edge in edges
        ],
    }
    return json.dumps(payload, indent=2, default=str).encode("utf-8")
