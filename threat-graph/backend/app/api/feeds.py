from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_analyst
from app.core.database import get_db
from app.models.feed import FeedConfig
from app.models.user import User
from app.schemas.threat import FeedConfigCreate, FeedConfigOut, FeedConfigUpdate
from app.services.feed_poller import poll_enabled_feeds, poll_feed

router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.get("", response_model=list[FeedConfigOut])
def list_feeds(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[FeedConfigOut]:
    feeds = list(db.scalars(select(FeedConfig).order_by(FeedConfig.created_at)).all())
    return [FeedConfigOut.model_validate(feed) for feed in feeds]


@router.post("", response_model=FeedConfigOut, status_code=status.HTTP_201_CREATED)
def create_feed(
    payload: FeedConfigCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> FeedConfigOut:
    existing = db.scalar(select(FeedConfig).where(FeedConfig.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Feed name already exists")
    feed = FeedConfig(**payload.model_dump())
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return FeedConfigOut.model_validate(feed)


@router.patch("/{feed_id}", response_model=FeedConfigOut)
def update_feed(
    feed_id: str,
    payload: FeedConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> FeedConfigOut:
    feed = db.get(FeedConfig, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(feed, key, value)
    db.commit()
    db.refresh(feed)
    return FeedConfigOut.model_validate(feed)


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed(
    feed_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    feed = db.get(FeedConfig, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    db.delete(feed)
    db.commit()


@router.post("/{feed_id}/poll")
def poll(
    feed_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst),
) -> dict:
    return poll_feed(db, feed_id)


@router.post("/poll-enabled")
def poll_all(
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst),
) -> list[dict]:
    return poll_enabled_feeds(db)
