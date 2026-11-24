from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.graph.factory import get_graph_store
from app.models.user import User
from app.schemas.report import ReportRequest
from app.services.reports import generate_pdf, graph_json, indicators_csv, relationships_csv

router = APIRouter(tags=["reports"])


def download(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/reports/pdf")
def pdf_report(
    payload: ReportRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    return download(generate_pdf(db, payload), "application/pdf", "threatgraph-report.pdf")


@router.get("/exports/indicators.csv")
def export_indicators(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    return download(indicators_csv(db), "text/csv", "threatgraph-indicators.csv")


@router.get("/exports/relationships.csv")
def export_relationships(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    return download(relationships_csv(db), "text/csv", "threatgraph-relationships.csv")


@router.get("/exports/graph.json")
def export_graph(
    _: User = Depends(get_current_user),
) -> Response:
    return download(graph_json(), "application/json", "threatgraph-graph.json")


@router.get("/exports/graph.graphml")
def export_graphml(
    _: User = Depends(get_current_user),
) -> Response:
    path = settings.backend_root / "storage" / "exports" / "threatgraph-graph.graphml"
    get_graph_store().export_graphml(path)
    return download(path.read_bytes(), "application/graphml+xml", "threatgraph-graph.graphml")
