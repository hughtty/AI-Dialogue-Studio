"""
models/project.py — 项目表
"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="未命名项目")

    # draft | voicing | video_pending | done
    status: Mapped[str] = mapped_column(String(20), default="draft")

    # 项目音色映射：{ "助理": { "voice_id": "...", "source": "design", "speed": 0.9, ... } }
    voices: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关联
    lines:      Mapped[list["Line"]]      = relationship("Line",      back_populates="project", cascade="all, delete-orphan", order_by="Line.index")
    video_jobs: Mapped[list["VideoJob"]]  = relationship("VideoJob",  back_populates="project", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "title":      self.title,
            "status":     self.status,
            "voices":     self.voices or {},
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "line_count": len(self.lines) if self.lines else 0,
        }
