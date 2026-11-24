from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.ingestion.service import ingest_bytes
from app.models.enums import FeedType
from app.models.feed import FeedConfig

EXTENSIONS = {
    FeedType.STIX: "json",
    FeedType.TAXII: "json",
    FeedType.JSON: "json",
    FeedType.CSV: "csv",
    FeedType.LOG: "log",
}


def _feed_url(feed: FeedConfig) -> str:
    if feed.feed_type == FeedType.TAXII and feed.collection_id:
        return f"{feed.url.rstrip('/')}/collections/{feed.collection_id}/objects/"
    return feed.url


def poll_feed(db: Session, feed_id: str) -> dict[str, Any]:
    feed = db.get(FeedConfig, feed_id)
    if not feed:
        raise NotFoundError("Threat intelligence feed not found")

    headers = {"Accept": "application/stix+json" if feed.feed_type in {FeedType.STIX, FeedType.TAXII} else "*/*"}
    if feed.auth_header_env:
        token = os.getenv(feed.auth_header_env)
        if not token:
            feed.last_status = "failed"
            feed.last_error = f"Environment variable {feed.auth_header_env} is not configured"
            feed.last_polled_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
            raise ValidationError(feed.last_error)
        headers["Authorization"] = token

    try:
        response = requests.get(_feed_url(feed), headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        feed.last_status = "failed"
        feed.last_error = str(exc)
        feed.last_polled_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
        raise ValidationError(f"Feed request failed: {exc}") from exc

    filename = f"{feed.name.replace(' ', '_')}.{EXTENSIONS.get(feed.feed_type, 'json')}"
    result = ingest_bytes(
        db,
        response.content,
        filename=filename,
        source=f"feed:{feed.name}",
        format_hint=feed.feed_type.value,
    )
    feed.last_polled_at = datetime.now(UTC).replace(tzinfo=None)
    feed.last_status = result.status
    feed.last_error = None if not result.errors else str(result.errors[:3])
    db.commit()
    return {"feed_id": feed.id, "feed_name": feed.name, **result.to_dict()}


def poll_enabled_feeds(db: Session) -> list[dict[str, Any]]:
    enabled = list(db.scalars(select_feeds_enabled()).all())
    return [poll_feed(db, feed.id) for feed in enabled]


def select_feeds_enabled():
    from sqlalchemy import select

    return select(FeedConfig).where(FeedConfig.enabled.is_(True))
