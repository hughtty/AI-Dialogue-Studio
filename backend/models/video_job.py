"""
models/video_job.py — 视频生成任务表
"""
import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )

    # MiniMax 异步 TTS 任务 ID
    tts_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 合并后的音频文件路径
    merged_audio: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 时间戳字幕数据：[{ text, start_ms, end_ms, speaker }]
    timestamps: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # 最终视频文件路径
    video_file: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # queued | tts_pending | tts_done | rendering | done | error
    status: Mapped[str] = mapped_column(String(20), default="queued")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project: Mapped["Project"] = relationship("Project", back_populates="video_jobs")

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "project_id":   self.project_id,
            "tts_task_id":  self.tts_task_id,
            "merged_audio": self.merged_audio,
            "video_file":   self.video_file,
            "status":       self.status,
            "error_msg":    self.error_msg,
            "created_at":   self.created_at.isoformat(),
        }
