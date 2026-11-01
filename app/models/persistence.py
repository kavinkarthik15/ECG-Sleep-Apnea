from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VisitorSession(Base):
    __tablename__ = "visitor_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'expired')", name="ck_visitor_sessions_status"),
        CheckConstraint("expires_at > created_at", name="ck_visitor_sessions_expiry"),
        Index("ix_visitor_sessions_status_expiry_activity", "status", "expires_at", "last_activity_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    analyses: Mapped[list["ECGAnalysis"]] = relationship(
        back_populates="visitor_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ECGAnalysis(Base):
    __tablename__ = "ecg_analyses"
    __table_args__ = (
        CheckConstraint("sampling_rate > 0", name="ck_ecg_analyses_sampling_rate"),
        CheckConstraint("window_seconds > 0", name="ck_ecg_analyses_window_seconds"),
        CheckConstraint("ignored_samples >= 0", name="ck_ecg_analyses_ignored_samples"),
        Index("ix_ecg_analyses_session_created", "visitor_session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_ref: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    visitor_session_id: Mapped[int] = mapped_column(
        ForeignKey("visitor_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    sampling_rate: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    window_seconds: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ignored_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    ignored_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    windows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)

    visitor_session: Mapped[VisitorSession] = relationship(back_populates="analyses")
