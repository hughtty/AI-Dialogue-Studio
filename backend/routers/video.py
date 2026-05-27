"""
routers/video.py — 视频合成
- POST /api/video/projects/{pid}/render  提交渲染任务
- GET  /api/video/jobs/{jid}             查询任务状态
"""
import asyncio
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ..core.config import STORAGE_DIR
from ..core.database import get_db, SessionLocal
from ..models import Project, Line, VideoJob
from ..services import composition, storage

router = APIRouter(prefix="/video", tags=["video"])


@router.post("/projects/{project_id}/render")
async def render_project(project_id: str, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "项目不存在")

    all_lines = sorted(p.lines, key=lambda l: l.index)
    if not all_lines:
        raise HTTPException(400, "没有台词")

    missing = [l for l in all_lines if l.audio_status != "done" or not l.audio_file]
    if missing:
        raise HTTPException(400, f"还有 {len(missing)} 条台词未配音")

    # 创建 VideoJob
    job = VideoJob(project_id=project_id, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)

    # 启动后台渲染
    asyncio.create_task(_do_render(project_id, job.id))

    return {"job_id": job.id, "status": "queued"}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(VideoJob, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    result = job.to_dict()
    if job.video_file:
        # 转换为可访问的 URL
        result["video_url"] = f"/storage/{job.project_id}/video/{job_id}.mp4"
    return result


async def _do_render(project_id: str, job_id: str):
    """后台执行视频渲染。"""
    db = SessionLocal()
    try:
        job = db.get(VideoJob, job_id)
        if not job:
            return

        job.status = "rendering"
        db.commit()

        project = db.get(Project, project_id)
        lines = sorted(project.lines, key=lambda l: l.index)

        # 生成 composition
        comp_dir = STORAGE_DIR / project_id / "composition"
        bgm_root = Path(__file__).parent.parent / "bgm"
        composition.build_composition(
            comp_dir=comp_dir,
            lines=lines,
            title=project.title,
            subtitle="所有对话记录均来自「助理」应用",
            bgm_root=bgm_root,
        )

        # 调用 HyperFrames render
        out_path = storage.video_path(project_id, job_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        proc = await asyncio.create_subprocess_exec(
            "npx", "hyperframes", "render", str(comp_dir),
            "--output", str(out_path),
            "--fps", "30",
            "--quality", "standard",
            "--format", "mp4",
            "--quiet",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[:500] if stderr else "渲染进程异常退出"
            raise RuntimeError(err)

        if not out_path.exists():
            raise RuntimeError("渲染完成但未找到输出文件")

        job.video_file = str(out_path)
        job.status = "done"
        db.commit()

    except asyncio.TimeoutError:
        if job:
            job.status = "error"
            job.error_msg = "渲染超时（超过 10 分钟）"
            db.commit()
    except Exception as e:
        if job:
            job.status = "error"
            job.error_msg = str(e)[:500]
            db.commit()
    finally:
        db.close()
