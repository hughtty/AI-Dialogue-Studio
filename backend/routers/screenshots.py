"""
routers/screenshots.py — 截图生成
- POST /api/screenshots/projects/{pid}/generate        生成全部/单页截图
- POST /api/screenshots/projects/{pid}/preview-html    预览单页 HTML
- GET  /api/screenshots/projects/{pid}                 列出截图
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import STORAGE_DIR
from ..core.database import get_db
from ..models import Project
from ..services import xiaohongshu_cards, screenshot as ss

router = APIRouter(prefix="/screenshots", tags=["screenshots"])


class PreviewRequest(BaseModel):
    page: int = 0
    ratio: str = "xhs-3-4"


class GenerateRequest(BaseModel):
    page: int | None = None
    ratio: str = "xhs-3-4"
    force: bool = False


def _ensure_html_and_png_dirs(project_id: str):
    html_dir = STORAGE_DIR / project_id / "screenshots" / "html"
    png_dir = STORAGE_DIR / project_id / "screenshots" / "png"
    html_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)
    return html_dir, png_dir


@router.post("/projects/{project_id}/preview-html")
def preview_html(project_id: str, body: PreviewRequest, db: Session = Depends(get_db)):
    """返回单页截图的 HTML 字符串用于前端预览。"""
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "项目不存在")

    all_lines = sorted(p.lines, key=lambda l: l.index)
    if not all_lines:
        raise HTTPException(400, "没有台词")

    slides = xiaohongshu_cards._group_slides(all_lines, body.ratio)
    page = body.page
    if page < 0 or page >= len(slides):
        raise HTTPException(400, f"页码超出范围，共 {len(slides)} 页")

    preset = xiaohongshu_cards.get_preset(body.ratio)
    html_content = xiaohongshu_cards.build_slide_html(
        slides[page], slide_num=page + 1, title=p.title, ratio_key=body.ratio
    )
    return {
        "ok": True,
        "html": html_content,
        "width": preset["width"],
        "height": preset["height"],
        "page": page,
        "total_pages": len(slides),
    }


@router.post("/projects/{project_id}/generate")
def generate_screenshots(
    project_id: str,
    body: GenerateRequest,
    db: Session = Depends(get_db),
):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "项目不存在")

    all_lines = sorted(p.lines, key=lambda l: l.index)
    if not all_lines:
        raise HTTPException(400, "没有台词")

    slides = xiaohongshu_cards._group_slides(all_lines, body.ratio)
    html_dir, png_dir = _ensure_html_and_png_dirs(project_id)

    page = body.page
    force = body.force

    if page is not None:
        # 生成单页
        if page >= len(slides):
            raise HTTPException(400, f"页码超出范围，共 {len(slides)} 页")
        html_path = html_dir / f"slide_{page + 1:02d}.html"
        xiaohongshu_cards.write_slide_html(slides[page], slide_num=page + 1, out_path=html_path, title=p.title, ratio_key=body.ratio)
        png_path = png_dir / f"{page + 1:02d}.png"
        ss.screenshot_single(html_path, png_path, force=force)
        return {
            "ok": True,
            "page": page,
            "total_pages": len(slides),
            "url": f"/storage/{project_id}/screenshots/png/{png_path.name}",
        }

    # 生成全部
    html_paths = xiaohongshu_cards.write_screenshots(all_lines, html_dir, title=p.title, ratio_key=body.ratio)
    png_paths = ss.batch_screenshots(html_paths, png_dir, force=force)

    urls = [f"/storage/{project_id}/screenshots/png/{p.name}" for p in png_paths]
    return {"ok": True, "count": len(urls), "urls": urls, "total_pages": len(slides)}


@router.get("/projects/{project_id}")
def list_screenshots(project_id: str):
    png_dir = STORAGE_DIR / project_id / "screenshots" / "png"
    if not png_dir.exists():
        return {"urls": []}
    urls = sorted(
        [f"/storage/{project_id}/screenshots/png/{p.name}" for p in png_dir.glob("*.png")]
    )
    return {"urls": urls}
