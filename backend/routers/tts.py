"""
routers/tts.py — MiniMax TTS 同步配音
- POST /api/tts/preview               任意文本试听
- POST /api/tts/lines/{line_id}       单句配音
- POST /api/tts/projects/{pid}/batch  批量配音（SSE 流）
- DELETE /api/tts/lines/{line_id}/audio  删除单句音频
"""
import asyncio
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db, SessionLocal
from ..models import Project, Line
from ..services import minimax, storage

router = APIRouter(prefix="/tts", tags=["tts"])

BATCH_CONCURRENCY = 2
MAX_RETRY = 3


# ── Schemas ───────────────────────────────────────────────────
class PreviewRequest(BaseModel):
    text: str
    voice_id: str
    speed: float = 0.9
    vol: float = 1.0
    pitch: int = 0
    emotion: str | None = None


# ── 工具：调一次 MiniMax 同步 TTS（含指数退避重试）──────────────
async def _tts_with_retry(text: str, voice_id: str, output_path, speed, vol, pitch, emotion=None) -> int:
    """调用 MiniMax TTS，对 429/5xx 做指数退避重试（1s → 2s → 4s）。"""
    last_err = None
    for attempt in range(MAX_RETRY + 1):
        try:
            return await minimax.tts_sync(
                text=text, voice_id=voice_id, output_path=output_path,
                speed=speed, vol=vol, pitch=pitch, emotion=emotion,
            )
        except httpx.HTTPStatusError as e:
            last_err = e
            code = e.response.status_code
            # 429 限流和 5xx 服务端错误都重试；4xx 客户端错误不重试
            if (code < 500 and code != 429) or attempt == MAX_RETRY:
                raise
            wait = 2 ** attempt + 1  # 1s, 2s, 4s
            await asyncio.sleep(wait)
        except httpx.HTTPError as e:
            last_err = e
            if attempt == MAX_RETRY:
                raise
            await asyncio.sleep(2 ** attempt + 1)
        except RuntimeError as e:
            # MiniMax 在 200 OK 中返回 RPM 限流错误，用更长间隔重试
            last_err = e
            if "rate limit" not in str(e).lower() or attempt == MAX_RETRY:
                raise
            wait = 5 * (attempt + 1)  # 5s, 10s, 15s
            await asyncio.sleep(wait)
    raise last_err  # pragma: no cover


def _voice_params(project: Project, speaker: str) -> dict | None:
    cfg = (project.voices or {}).get(speaker)
    if not cfg or not cfg.get("voice_id"):
        return None
    return {
        "voice_id": cfg["voice_id"],
        "speed": float(cfg.get("speed", 0.9)),
        "vol":   float(cfg.get("vol", 1.0)),
        "pitch": int(cfg.get("pitch", 0)),
    }


# ── 试听 ──────────────────────────────────────────────────────
@router.post("/preview")
async def preview(body: PreviewRequest):
    storage.cleanup_old_previews()
    if not body.text.strip():
        raise HTTPException(400, "试听文本不能为空")
    if not body.voice_id:
        raise HTTPException(400, "voice_id 不能为空")
    path, url = storage.new_preview_path()
    try:
        duration_ms = await _tts_with_retry(
            text=body.text, voice_id=body.voice_id, output_path=path,
            speed=body.speed, vol=body.vol, pitch=body.pitch, emotion=body.emotion,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"MiniMax 返回错误：{e.response.status_code} {e.response.text[:200]}")
    except Exception as e:
        raise HTTPException(500, f"试听失败：{e}")
    return {"audio_url": url, "duration_ms": duration_ms}


# ── 单句配音 ──────────────────────────────────────────────────
@router.post("/lines/{line_id}")
async def tts_one_line(line_id: str, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(404, "台词不存在")
    project = db.get(Project, line.project_id)
    params = _voice_params(project, line.speaker)
    if not params:
        raise HTTPException(400, f"角色「{line.speaker}」未配置 voice_id")
    if not line.text_clean.strip():
        raise HTTPException(400, "台词为空")

    line.audio_status = "generating"
    line.error_msg = None
    db.commit()

    # 删除旧音频（确保重新生成时文件是最新的）
    storage.delete_line_audio(line.project_id, line.id)
    path = storage.audio_path(line.project_id, line.id)
    emotion = line.emotion
    try:
        duration_ms = await _tts_with_retry(
            text=line.text_clean, output_path=path, emotion=emotion, **params,
        )
    except Exception as e:
        line.audio_status = "error"
        line.error_msg = str(e)[:500]
        db.commit()
        raise HTTPException(502, f"配音失败：{e}")

    line.audio_file = str(path)
    line.duration_ms = duration_ms
    line.audio_status = "done"
    line.error_msg = None
    db.commit()
    db.refresh(line)
    return {
        **line.to_dict(),
        "audio_url": storage.url_for_audio(line.project_id, line.id),
    }


# ── 批量配音（SSE）────────────────────────────────────────────
@router.post("/projects/{project_id}/batch")
async def tts_batch(project_id: str, force: bool = Query(False)):
    """SSE 流：逐条推送进度。事件 data 为 JSON。"""

    async def event_stream():
        # 用独立 session，避免 SSE 长连接占用 request session
        db = SessionLocal()
        try:
            project = db.get(Project, project_id)
            if not project:
                yield _sse({"type": "error", "message": "项目不存在"})
                return

            all_lines = sorted(project.lines, key=lambda l: l.index)
            targets = [l for l in all_lines if force or l.audio_status != "done"]
            total = len(targets)
            yield _sse({"type": "start", "total": total, "skipped": len(all_lines) - total})

            if total == 0:
                yield _sse({"type": "done", "ok": 0, "failed": 0})
                return

            # 校验音色配置
            missing = sorted({l.speaker for l in targets if not _voice_params(project, l.speaker)})
            if missing:
                yield _sse({"type": "error", "message": f"未配置 voice_id 的角色：{', '.join(missing)}"})
                return

            sem = asyncio.Semaphore(BATCH_CONCURRENCY)
            queue: asyncio.Queue = asyncio.Queue()
            done_count = {"ok": 0, "fail": 0}

            async def worker(line_id: str):
                async with sem:
                    # 每个 worker 用自己的 session，避免并发冲突
                    wdb = SessionLocal()
                    try:
                        ln = wdb.get(Line, line_id)
                        proj = wdb.get(Project, project_id)
                        params = _voice_params(proj, ln.speaker)
                        emotion = ln.emotion
                        ln.audio_status = "generating"
                        ln.error_msg = None
                        wdb.commit()
                        await queue.put({"type": "progress", "line_id": ln.id,
                                         "status": "generating", "speaker": ln.speaker})
                        # 防 RPM：每个 worker 调用前间隔 2.5s（约 24 条/分钟）
                        await asyncio.sleep(2.5)
                        # 删除旧音频
                        storage.delete_line_audio(project_id, ln.id)
                        path = storage.audio_path(project_id, ln.id)
                        try:
                            duration_ms = await _tts_with_retry(
                                text=ln.text_clean, output_path=path, emotion=emotion, **params,
                            )
                            ln.audio_file = str(path)
                            ln.duration_ms = duration_ms
                            ln.audio_status = "done"
                            ln.error_msg = None
                            wdb.commit()
                            done_count["ok"] += 1
                            await queue.put({
                                "type": "progress", "line_id": ln.id,
                                "status": "done", "speaker": ln.speaker,
                                "audio_url": storage.url_for_audio(project_id, ln.id),
                                "duration_ms": duration_ms,
                            })
                        except Exception as e:
                            ln.audio_status = "error"
                            ln.error_msg = str(e)[:500]
                            wdb.commit()
                            done_count["fail"] += 1
                            await queue.put({
                                "type": "progress", "line_id": ln.id,
                                "status": "error", "speaker": ln.speaker,
                                "error": str(e)[:200],
                            })
                    finally:
                        wdb.close()

            tasks = [asyncio.create_task(worker(l.id)) for l in targets]
            finisher = asyncio.ensure_future(asyncio.gather(*tasks))

            sent = 0
            while sent < total:
                evt = await queue.get()
                yield _sse(evt)
                if evt["type"] == "progress" and evt["status"] in ("done", "error"):
                    sent += 1

            await finisher
            yield _sse({"type": "done", "ok": done_count["ok"], "failed": done_count["fail"]})
        finally:
            db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ── 删除单句音频 ──────────────────────────────────────────────
@router.delete("/lines/{line_id}/audio", status_code=204)
def delete_line_audio(line_id: str, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(404, "台词不存在")
    path = storage.audio_path(line.project_id, line.id)
    if path.exists():
        path.unlink()
    line.audio_file = None
    line.duration_ms = None
    line.audio_status = "pending"
    line.error_msg = None
    db.commit()


# ── 清理项目缓存 ──────────────────────────────────────────────
@router.delete("/projects/{project_id}/cache")
def clear_cache(project_id: str, db: Session = Depends(get_db)):
    """清理项目临时文件（composition、video、旧试听音频），保留 audio 和 screenshots。"""
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    stats = storage.cleanup_project_cache(project_id)
    return {"ok": True, **stats}
