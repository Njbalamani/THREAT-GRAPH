from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import FeedType
from app.models.user import new_id, utcnow


class FeedConfig(Base):
    __tablename__ = "feed_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    feed_type: Mapped[FeedType] = mapped_column(Enum(FeedType), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    collection_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_header_env: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
