"""
services/storage.py — 文件存储服务
规范路径：storage/{project_id}/audio/{line_id}.mp3
         storage/{project_id}/video/{job_id}.mp4
"""
import shutil
import time
import uuid
from pathlib import Path
from ..core.config import STORAGE_DIR

PREVIEW_DIR = STORAGE_DIR / "_preview"
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)


def _project_dir(project_id: str) -> Path:
    d = STORAGE_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def audio_path(project_id: str, line_id: str) -> Path:
    d = _project_dir(project_id) / "audio"
    d.mkdir(exist_ok=True)
    return d / f"{line_id}.mp3"


def merged_audio_path(project_id: str, job_id: str) -> Path:
    d = _project_dir(project_id) / "audio"
    d.mkdir(exist_ok=True)
    return d / f"merged_{job_id}.mp3"


def video_path(project_id: str, job_id: str) -> Path:
    d = _project_dir(project_id) / "video"
    d.mkdir(exist_ok=True)
    return d / f"{job_id}.mp4"


def card_export_path(project_id: str) -> Path:
    d = _project_dir(project_id) / "cards"
    d.mkdir(exist_ok=True)
    return d


def delete_project_files(project_id: str):
    """删除项目所有文件"""
    d = STORAGE_DIR / project_id
    if d.exists():
        shutil.rmtree(d)


def delete_line_audio(project_id: str, line_id: str) -> None:
    """删除单句音频文件（重新生成前调用）"""
    p = audio_path(project_id, line_id)
    if p.exists():
        p.unlink()


def cleanup_project_cache(project_id: str) -> dict:
    """清理项目临时文件（试听、composition、video），保留音频和截图。返回清理统计。"""
    stats = {"deleted": 0, "freed_bytes": 0}
    proj = STORAGE_DIR / project_id
    if not proj.exists():
        return stats

    # 清理 composition 中间文件
    comp = proj / "composition"
    if comp.exists():
        sz = sum(f.stat().st_size for f in comp.rglob("*") if f.is_file())
        shutil.rmtree(comp)
        stats["deleted"] += 1
        stats["freed_bytes"] += sz

    # 清理视频文件
    video = proj / "video"
    if video.exists():
        sz = sum(f.stat().st_size for f in video.iterdir() if f.is_file())
        for f in video.iterdir():
            if f.is_file():
                f.unlink()
        stats["deleted"] += 1
        stats["freed_bytes"] += sz

    # 清理全局试听缓存（超过 5 分钟的）
    cleanup_old_previews(ttl_seconds=300)

    return stats


def url_for_audio(project_id: str, line_id: str) -> str:
    """返回前端可访问的 URL（相对路径，由后端路由提供服务）"""
    return f"/storage/{project_id}/audio/{line_id}.mp3"


def url_for_video(project_id: str, job_id: str) -> str:
    return f"/storage/{project_id}/video/{job_id}.mp4"


def new_preview_path() -> tuple[Path, str]:
    """生成一个新的试听音频路径，返回 (本地路径, URL)"""
    name = f"{uuid.uuid4()}.mp3"
    return PREVIEW_DIR / name, f"/storage/_preview/{name}"


def cleanup_old_previews(ttl_seconds: int = 3600) -> None:
    """删除超过 ttl 的试听音频"""
    now = time.time()
    for f in PREVIEW_DIR.glob("*.mp3"):
        try:
            if now - f.stat().st_mtime > ttl_seconds:
                f.unlink()
        except OSError:
            pass
