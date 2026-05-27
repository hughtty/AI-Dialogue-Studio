"""
routers/story.py — 故事生成与导入
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import json, re

from ..core.database import get_db
from ..models import Project, Line
from ..services.story import generate_story

router = APIRouter(prefix="/story", tags=["story"])


class GenerateRequest(BaseModel):
    project_id: str
    theme: str
    tone: str = "留白向"
    ai_style: str = "陪伴感"
    characters: str = "一个在外地工作的中年人"


class ImportRequest(BaseModel):
    project_id: str
    story_json: dict


_TAG_RE = re.compile(r"<#[\d.]+#>")
_SOUND_RE = re.compile(
    r"[\[(](?:breath|sighs|laughs|chuckles|gasps|inhales|exhales|emm|"
    r"coughs|clear-throat|groans|pant|sniffs|snorts|burps|"
    r"lip-smacking|humming|hissing|sneezes)[\])]",
    re.IGNORECASE,
)

def strip_tags(text: str) -> str:
    """移除停顿标签 <#x#> 和语气词标签 (breath)/[sighs] 等，返回纯文本"""
    text = _TAG_RE.sub("", text)
    text = _SOUND_RE.sub("", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()


def _load_story_into_project(project_id: str, story: dict, db: Session):
    """将故事 JSON 写入数据库台词行"""
    # 清空旧台词
    db.query(Line).filter(Line.project_id == project_id).delete()

    idx = 0
    for slide in story.get("slides", []):
        for msg in slide.get("messages", []):
            line = Line(
                project_id=project_id,
                index=idx,
                speaker=msg.get("name", msg.get("role", "unknown")),
                role=msg.get("role", "user"),
                text_raw=msg.get("text", ""),
                text_clean=strip_tags(msg.get("text", "")),
                emotion=msg.get("emotion") or msg.get("default_emotion"),
            )
            db.add(line)
            idx += 1

    # 更新项目标题和状态
    p = db.get(Project, project_id)
    if p:
        if story.get("title"):
            p.title = story["title"]
        p.status = "draft"

    db.commit()


@router.post("/generate")
async def api_generate(body: GenerateRequest, db: Session = Depends(get_db)):
    p = db.get(Project, body.project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    try:
        story = await generate_story(
            theme=body.theme,
            tone=body.tone,
            ai_style=body.ai_style,
            characters=body.characters,
        )
        _load_story_into_project(body.project_id, story, db)
        return {"ok": True, "story": story}
    except Exception as e:
        raise HTTPException(500, f"生成失败：{str(e)}")


@router.post("/import")
def api_import(body: ImportRequest, db: Session = Depends(get_db)):
    p = db.get(Project, body.project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    try:
        _load_story_into_project(body.project_id, body.story_json, db)
        return {"ok": True, "line_count": db.query(Line).filter(Line.project_id == body.project_id).count()}
    except Exception as e:
        raise HTTPException(400, f"导入失败：{str(e)}")
