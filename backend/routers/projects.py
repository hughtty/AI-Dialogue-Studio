"""
routers/projects.py — 项目 CRUD
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..models import Project, Line
from ..services.storage import delete_project_files
import re

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Schemas ───────────────────────────────────────────────────
class ProjectCreate(BaseModel):
    title: str = "未命名项目"


class ProjectUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    voices: dict | None = None


class LineCreate(BaseModel):
    speaker: str
    role: str = "user"
    text_raw: str
    index: int | None = None
    emotion: str | None = None


class LineUpdate(BaseModel):
    speaker: str | None = None
    role: str | None = None
    text_raw: str | None = None
    index: int | None = None
    emotion: str | None = None
    audio_status: str | None = None


# ── 工具函数 ──────────────────────────────────────────────────
_TAG_RE = re.compile(r"<#[\d.]+#>")
_SOUND_RE = re.compile(
    r"[\[(](?:breath|sighs|laughs|chuckles|gasps|inhales|exhales|emm|"
    r"coughs|clear-throat|groans|pant|sniffs|snorts|burps|"
    r"lip-smacking|humming|hissing|sneezes)[\])]",
    re.IGNORECASE,
)


def strip_tags(text: str) -> str:
    """移除停顿标签 <#0.3#> 和语气词标签 (breath)/[sighs] 等，返回纯文本"""
    text = _TAG_RE.sub("", text)
    text = _SOUND_RE.sub("", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()


# ── 项目接口 ──────────────────────────────────────────────────
@router.get("")
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    return [p.to_dict() for p in projects]


@router.post("", status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(title=body.title)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project.to_dict()


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    return {**p.to_dict(), "lines": [l.to_dict() for l in p.lines]}


@router.patch("/{project_id}")
def update_project(project_id: str, body: ProjectUpdate, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    if body.title is not None:
        p.title = body.title
    if body.status is not None:
        p.status = body.status
    if body.voices is not None:
        p.voices = body.voices
    db.commit()
    db.refresh(p)
    return p.to_dict()


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    db.delete(p)
    db.commit()
    delete_project_files(project_id)


# ── 台词接口 ──────────────────────────────────────────────────
@router.get("/{project_id}/lines")
def get_lines(project_id: str, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    return [l.to_dict() for l in p.lines]


@router.post("/{project_id}/lines", status_code=201)
def create_line(project_id: str, body: LineCreate, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    # 自动计算 index
    max_idx = max((l.index for l in p.lines), default=-1)
    idx = body.index if body.index is not None else max_idx + 1
    line = Line(
        project_id=project_id,
        index=idx,
        speaker=body.speaker,
        role=body.role,
        text_raw=body.text_raw,
        text_clean=strip_tags(body.text_raw),
        emotion=body.emotion,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line.to_dict()


@router.patch("/{project_id}/lines/{line_id}")
def update_line(project_id: str, line_id: str, body: LineUpdate, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line or line.project_id != project_id:
        raise HTTPException(404, "台词不存在")
    if body.speaker is not None:
        line.speaker = body.speaker
    if body.role is not None:
        line.role = body.role
    if body.text_raw is not None:
        line.text_raw = body.text_raw
        line.text_clean = strip_tags(body.text_raw)
    if body.emotion is not None:
        line.emotion = body.emotion
    if body.index is not None:
        line.index = body.index
    if body.audio_status is not None:
        line.audio_status = body.audio_status
    db.commit()
    db.refresh(line)
    return line.to_dict()


@router.delete("/{project_id}/lines/{line_id}", status_code=204)
def delete_line(project_id: str, line_id: str, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line or line.project_id != project_id:
        raise HTTPException(404, "台词不存在")
    db.delete(line)
    db.commit()


@router.put("/{project_id}/lines/reorder")
def reorder_lines(project_id: str, order: list[str], db: Session = Depends(get_db)):
    """批量更新台词顺序，order 是 line_id 数组"""
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    for idx, line_id in enumerate(order):
        line = db.get(Line, line_id)
        if line and line.project_id == project_id:
            line.index = idx
    db.commit()
    return {"ok": True}
