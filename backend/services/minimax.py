"""
services/minimax.py — MiniMax API 客户端
封装 TTS 同步、TTS 异步、Voice Design、Voice Clone 四个接口
"""
import httpx
import base64
from pathlib import Path
from ..core.config import MINIMAX_API_KEY, MINIMAX_BASE_URL, MINIMAX_TTS_MODEL


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }


# ── 同步 TTS ──────────────────────────────────────────────────
async def tts_sync(
    text: str,
    voice_id: str,
    output_path: Path,
    speed: float = 1.0,
    vol: float = 1.0,
    pitch: int = 0,
    emotion: str | None = None,
) -> int:
    """
    同步语音合成，写入 MP3 文件。
    返回音频时长（毫秒）。
    """
    voice_setting = {
        "voice_id": voice_id,
        "speed": speed,
        "vol": vol,
        "pitch": pitch,
    }
    if emotion:
        voice_setting["emotion"] = emotion
    payload = {
        "model": MINIMAX_TTS_MODEL,
        "text": text,
        "voice_setting": voice_setting,
        "audio_setting": {
            "format": "mp3",
            "sample_rate": 32000,
            "bitrate": 128000,
            "channel": 1,
        },
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{MINIMAX_BASE_URL}/t2a_v2",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    # 检查 MiniMax 业务错误（200 OK 但返回错误 JSON）
    if "data" not in data:
        err_msg = data.get("message") or data.get("error") or str(data)
        raise RuntimeError(f"MiniMax TTS 错误：{err_msg}")

    # 解码 hex 音频
    audio_hex = data["data"]["audio"]
    audio_bytes = bytes.fromhex(audio_hex)
    output_path.write_bytes(audio_bytes)

    # 返回额外信息中的时长（毫秒），若无则用文件大小估算
    duration_ms = data.get("extra_info", {}).get("audio_length", 0)
    if not duration_ms:
        # 粗估：mp3 128kbps → 每字节约 0.0625ms
        duration_ms = int(len(audio_bytes) * 0.0625)

    return duration_ms


# ── 异步 TTS（含时间戳）────────────────────────────────────────
async def tts_async_submit(
    text: str,
    voice_id: str,
    speed: float = 1.0,
    vol: float = 1.0,
    pitch: int = 0,
) -> str:
    """
    提交异步 TTS 任务，返回 task_id。
    text 是合并的全部台词，每句之间用 \n 分隔。
    """
    payload = {
        "model": MINIMAX_TTS_MODEL,
        "text": text,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": vol,
            "pitch": pitch,
        },
        "audio_setting": {
            "format": "mp3",
            "audio_sample_rate": 32000,
            "bitrate": 128000,
            "channel": 1,
        },
        "timestamp_response": True,   # 关键：开启句级时间戳
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{MINIMAX_BASE_URL}/t2a_async_v2",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    return data["task_id"]


async def tts_async_query(task_id: str) -> dict:
    """
    查询异步 TTS 任务状态。
    返回 { status, file_id, timestamps } 或 { status: "Processing" }
    status 值：Processing | Success | Failed
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{MINIMAX_BASE_URL}/query/t2a_async_query_v2",
            headers=_headers(),
            params={"task_id": task_id},
        )
        resp.raise_for_status()
        return resp.json()


async def tts_async_download(file_id: str, output_path: Path) -> None:
    """下载异步 TTS 生成的音频文件"""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(
            f"{MINIMAX_BASE_URL}/files/retrieve-content",
            headers=_headers(),
            params={"file_id": file_id},
        )
        resp.raise_for_status()
        output_path.write_bytes(resp.content)


# ── Voice Design ──────────────────────────────────────────────
async def voice_design(
    description: str,
    sample_text: str,
    voice_id: str,
) -> dict:
    """
    用自然语言描述生成音色，返回 { voice_id, audio_sample_url }
    """
    payload = {
        "model": MINIMAX_TTS_MODEL,
        "voice_id": voice_id,
        "description": description,
        "text": sample_text,
        "audio_setting": {"format": "mp3", "sample_rate": 32000},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{MINIMAX_BASE_URL}/voice_design",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


# ── Voice Clone ───────────────────────────────────────────────
async def upload_clone_audio(audio_bytes: bytes, filename: str) -> str:
    """上传待克隆音频，返回 file_id"""
    files = {"file": (filename, audio_bytes, "audio/mpeg")}
    data  = {"purpose": "voice_clone"}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{MINIMAX_BASE_URL}/files/upload",
            headers={"Authorization": f"Bearer {MINIMAX_API_KEY}"},
            files=files,
            data=data,
        )
        resp.raise_for_status()
        return resp.json()["file"]["file_id"]


async def voice_clone(
    file_id: str,
    voice_id: str,
    sample_text: str,
) -> dict:
    """执行音色克隆，返回 { voice_id, demo_audio }"""
    payload = {
        "file_id": file_id,
        "voice_id": voice_id,
        "text": sample_text,
        "model": MINIMAX_TTS_MODEL,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{MINIMAX_BASE_URL}/voice_clone",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()
