from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_analyst
from app.core.database import get_db
from app.graph.factory import get_graph_store
from app.graph.relationships import build_relationships
from app.ml.pipeline import model_status, predict, train_model
from app.models.user import User
from app.schemas.analytics import AnalysisResult, PredictionOut, TrainResult
from app.services.graph_analytics import analyze_graph, persist_inferred_connections

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/graph/rebuild")
def rebuild_graph(
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst),
) -> dict:
    return build_relationships(db, rebuild=True)


@router.post("/graph/analyze", response_model=AnalysisResult)
def analyze(
    persist: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AnalysisResult:
    store = get_graph_store()
    result = analyze_graph(store)
    if persist:
        result["inferred_edges_created"] = persist_inferred_connections(db, store, result)
    return AnalysisResult.model_validate(result)


@router.post("/model/train", response_model=TrainResult)
def train(
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst),
) -> TrainResult:
    return TrainResult.model_validate(train_model(db, get_graph_store()))


@router.get("/model")
def get_model(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return model_status(db)


@router.get("/predictions", response_model=list[PredictionOut])
def get_predictions(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[PredictionOut]:
    return [PredictionOut.model_validate(item) for item in predict(db, get_graph_store())]
