"""
models/line.py — 台词行表
"""
import uuid
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class Line(Base):
    __tablename__ = "lines"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)      # 顺序编号

    speaker:    Mapped[str]  = mapped_column(String(50), nullable=False)
    # ai | user — 决定气泡显示位置（左/右），独立于 speaker 名字
    role:       Mapped[str]  = mapped_column(String(10), nullable=False, default="user")
    text_raw:   Mapped[str]  = mapped_column(Text, nullable=False)   # 含停顿标签
    text_clean: Mapped[str]  = mapped_column(Text, nullable=False)   # 纯文本（展示用）

    # 情感标签（speech-2.8-hd 支持: calm/happy/sad/angry/fearful/disgusted/surprised）
    emotion: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 配音结果
    audio_file:  Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # pending | generating | done | error
    audio_status: Mapped[str] = mapped_column(String(20), default="pending")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="lines")

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "project_id":   self.project_id,
            "index":        self.index,
            "speaker":      self.speaker,
            "role":         self.role,
            "text_raw":     self.text_raw,
            "text_clean":   self.text_clean,
            "emotion":      self.emotion,
            "audio_file":   self.audio_file,
            "duration_ms":  self.duration_ms,
            "audio_status": self.audio_status,
            "error_msg":    self.error_msg,
        }
