"""
fast/tts.py — MiniMax 同步 TTS（独立版）
支持 emotion、语气词标签、停顿标签。
"""
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_API_KEY = os.getenv("MINIMAX_API_KEY", "")
_BASE = "https://api.minimaxi.com/v1"
_MODEL = "speech-2.8-hd"


def tts_sync(text: str, voice_id: str, output_path: Path,
             speed: float = 0.95, vol: float = 1.0, pitch: int = 0,
             emotion: str = "calm") -> int:
    """合成 mp3，返回时长 ms。同步阻塞调用。

    text 中可包含 MiniMax 原生支持的标签：
    - <#x#> 停顿控制（x 为秒）
    - (breath), (sighs), (laughs), (chuckles), (gasps) 等语气词
    """
    # 避免触发 RPM 限制
    time.sleep(1.2)

    payload = {
        "model": _MODEL,
        "text": text,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": vol,
            "pitch": pitch,
            "emotion": emotion,
        },
        "audio_setting": {"format": "mp3", "sample_rate": 32000, "bitrate": 128000, "channel": 1},
    }

    last_err = None
    for attempt in range(3):
        with httpx.Client(timeout=60) as c:
            r = c.post(f"{_BASE}/t2a_v2",
                       headers={"Authorization": f"Bearer {_API_KEY}", "Content-Type": "application/json"},
                       json=payload)
            r.raise_for_status()
            data = r.json()
        base_resp = data.get("base_resp", {})
        if base_resp.get("status_code", 0) != 0:
            last_err = f"MiniMax error {base_resp.get('status_code')}: {base_resp.get('status_msg')}"
            time.sleep(1.5 * (attempt + 1))
            continue
        if "data" not in data or "audio" not in data["data"]:
            last_err = f"Unexpected response keys: {list(data.keys())}"
            time.sleep(1.5 * (attempt + 1))
            continue
        audio = bytes.fromhex(data["data"]["audio"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio)
        duration_ms = data.get("extra_info", {}).get("audio_length", 0) or int(len(audio) * 0.0625)
        return duration_ms
    raise RuntimeError(f"TTS failed after 3 retries: {last_err}")
