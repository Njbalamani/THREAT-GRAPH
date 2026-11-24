from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ValidationError
from app.graph.base import GraphStore
from app.ml.features import FEATURE_NAMES, build_feature_rows, matrix
from app.models.threat import MLModelRun


def _artifact_path(version: str) -> Path:
    settings.model_path.mkdir(parents=True, exist_ok=True)
    return settings.model_path / f"{version}.joblib"


def _latest_run(db: Session) -> MLModelRun | None:
    return db.scalar(select(MLModelRun).order_by(desc(MLModelRun.created_at)))


def train_model(db: Session, store: GraphStore) -> dict[str, Any]:
    rows = build_feature_rows(db, store)
    if len(rows) < 2:
        raise ValidationError("At least two indicators are required to train the risk model")

    X = matrix(rows)
    y = np.asarray([row["label"] for row in rows], dtype=int)
    classes, counts = np.unique(y, return_counts=True)
    if len(classes) < 2:
        ordered = sorted(range(len(rows)), key=lambda index: rows[index]["features"]["severity_score"])
        split_at = max(1, len(ordered) // 2)
        for index in ordered[:split_at]:
            y[index] = 0
        for index in ordered[split_at:]:
            y[index] = 1

    if len(rows) >= 10:
        stratify: np.ndarray | None = y
        if min(np.unique(y, return_counts=True)[1]) < 2:
            stratify = None
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=stratify)
        evaluation_rows = len(y_test)
    else:
        X_train, X_test, y_train, y_test = X, X, y, y
        evaluation_rows = 0

    classifier = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        random_state=42,
        class_weight="balanced_subsample",
        n_jobs=1,
    )
    model = Pipeline([("scaler", StandardScaler()), ("classifier", classifier)])
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    accuracy = float(accuracy_score(y_test, predictions))
    metrics: dict[str, Any] = {
        "accuracy": round(accuracy, 4),
        "evaluation_rows": evaluation_rows,
        "training_rows": len(y_train),
    }
    if len(np.unique(y_test)) == 2:
        try:
            metrics["roc_auc"] = round(float(roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])), 4)
        except ValueError:
            pass

    cluster_model = None
    cluster_scaler = None
    cluster_sizes: dict[str, int] = {}
    if len(rows) >= 3:
        cluster_scaler = StandardScaler()
        scaled = cluster_scaler.fit_transform(X)
        n_clusters = min(6, max(2, len(rows) // 3), len(rows))
        cluster_model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = cluster_model.fit_predict(scaled)
        unique_labels, counts = np.unique(labels, return_counts=True)
        cluster_sizes = {str(label): int(count) for label, count in zip(unique_labels, counts, strict=True)}

    version = f"rf-{datetime.now(UTC).replace(tzinfo=None).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    path = _artifact_path(version)
    artifact = {
        "version": version,
        "features": FEATURE_NAMES,
        "model": model,
        "cluster_model": cluster_model,
        "cluster_scaler": cluster_scaler,
        "feature_means": X.mean(axis=0).tolist(),
        "cluster_sizes": cluster_sizes,
        "metrics": metrics,
        "trained_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
    }
    joblib.dump(artifact, path)

    label_source = "analyst_or_trusted_feed" if any(row["label_source"] != "heuristic" for row in rows) else "heuristic"
    run = MLModelRun(
        version=version,
        model_type="RandomForestClassifier",
        metrics={**metrics, "cluster_sizes": cluster_sizes},
        features=FEATURE_NAMES,
        training_samples=len(rows),
        label_source=label_source,
        artifact_path=str(path),
    )
    db.add(run)
    db.commit()

    return {
        "version": version,
        "training_samples": len(rows),
        "metrics": metrics,
        "features": FEATURE_NAMES,
        "label_source": label_source,
        "note": "Predictions are advisory and must be verified by an analyst before being treated as confirmed.",
    }


def _load_artifact(db: Session, store: GraphStore) -> dict[str, Any]:
    run = _latest_run(db)
    if run is None:
        train_model(db, store)
        run = _latest_run(db)
    if run is None:
        raise ValidationError("Model training did not produce a usable model")
    artifact = joblib.load(run.artifact_path)
    artifact["model_version"] = run.version
    return artifact


def _risk_level(probability: float) -> str:
    if probability >= 0.8:
        return "critical"
    if probability >= 0.6:
        return "high"
    if probability >= 0.35:
        return "medium"
    return "low"


def _explain(artifact: dict[str, Any], vector: list[float], probability: float) -> list[str]:
    model = artifact["model"]
    classifier = model.named_steps["classifier"]
    importances = list(classifier.feature_importances_)
    means = artifact.get("feature_means", [0.0] * len(importances))
    ranked = sorted(
        zip(importances, FEATURE_NAMES, vector, means, strict=False),
        key=lambda item: item[0],
        reverse=True,
    )
    explanations: list[str] = []
    for importance, name, value, mean in ranked[:3]:
        if float(value) > float(mean):
            explanations.append(f"Elevated {name.replace('_', ' ')} ({float(value):.2f}) increased the score.")
        else:
            explanations.append(f"{name.replace('_', ' ')} contributed {float(importance) * 100:.1f}% to the model.")
    explanations.append(f"Predicted probability {probability:.1%}; model output only, not a confirmed attack.")
    return explanations


def predict(db: Session, store: GraphStore, *, limit: int = 500) -> list[dict[str, Any]]:
    rows = build_feature_rows(db, store)
    if not rows:
        return []
    artifact = _load_artifact(db, store)
    X = matrix(rows)
    probabilities = artifact["model"].predict_proba(X)[:, 1]

    cluster_labels: np.ndarray | None = None
    if artifact.get("cluster_model") and artifact.get("cluster_scaler"):
        scaled = artifact["cluster_scaler"].transform(X)
        cluster_labels = artifact["cluster_model"].predict(scaled)

    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        indicator = row["indicator"]
        probability = float(probabilities[index])
        cluster_id = int(cluster_labels[index]) if cluster_labels is not None else None
        cluster_size = artifact.get("cluster_sizes", {}).get(str(cluster_id)) if cluster_id is not None else None
        results.append(
            {
                "indicator_id": indicator.id,
                "value": indicator.value,
                "type": indicator.type.value,
                "probability": round(probability, 4),
                "risk_level": _risk_level(probability),
                "cluster_id": cluster_id,
                "cluster_size": cluster_size,
                "confirmed": False,
                "prediction_only": True,
                "explanation": _explain(artifact, row["vector"], probability),
                "model_version": artifact["model_version"],
            }
        )
    results.sort(key=lambda item: item["probability"], reverse=True)
    return results[:limit]


def model_status(db: Session) -> dict[str, Any]:
    run = _latest_run(db)
    if not run:
        return {"trained": False}
    return {
        "trained": True,
        "version": run.version,
        "model_type": run.model_type,
        "metrics": run.metrics,
        "features": run.features,
        "training_samples": run.training_samples,
        "label_source": run.label_source,
        "artifact_path": run.artifact_path,
        "created_at": run.created_at.isoformat(),
    }


def metadata_payload(db: Session) -> dict[str, Any]:
    return model_status(db)


def write_metadata(db: Session) -> str:
    metadata = json.dumps(metadata_payload(db), indent=2, default=str)
    path = settings.model_path / "model_registry.json"
    settings.model_path.mkdir(parents=True, exist_ok=True)
    path.write_text(metadata, encoding="utf-8")
    return str(path)
