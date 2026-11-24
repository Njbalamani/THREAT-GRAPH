from pydantic import BaseModel

from app.models.enums import Provenance


class AnomalyOut(BaseModel):
    source: str
    target: str
    relationship: str
    provenance: Provenance
    score: float
    reason: str


class ClusterOut(BaseModel):
    cluster_id: int
    size: int
    nodes: list[str]
    labels: list[str]
    risk_score: float


class ImportantNodeOut(BaseModel):
    key: str
    label: str
    type: str
    score: float
    degree: int


class AnalysisResult(BaseModel):
    backend: str
    node_count: int
    edge_count: int
    clusters: list[ClusterOut]
    important_nodes: list[ImportantNodeOut]
    anomalies: list[AnomalyOut]
    generated_at: str


class PredictionOut(BaseModel):
    indicator_id: str
    value: str
    type: str
    probability: float
    risk_level: str
    cluster_id: int | None = None
    cluster_size: int | None = None
    confirmed: bool = False
    prediction_only: bool = True
    explanation: list[str]
    model_version: str


class TrainResult(BaseModel):
    version: str
    training_samples: int
    metrics: dict
    features: list[str]
    label_source: str
    note: str
