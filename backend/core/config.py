"""
core/config.py — 全局配置，从环境变量读取
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── 基础路径 ──────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── AI 服务密钥 ──────────────────────────────
MINIMAX_API_KEY:    str = os.getenv("MINIMAX_API_KEY", "")
MOONSHOT_API_KEY:   str = os.getenv("MOONSHOT_API_KEY", "")
CLAUDE_API_KEY:     str = os.getenv("CLAUDE_API_KEY", "")

MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"
MINIMAX_TTS_MODEL = "speech-2.8-hd"

MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"
MOONSHOT_MODEL = "kimi-k2.6"

# ── 数据库 ────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/dialogue.db")

# ── 文件存储 ──────────────────────────────────
STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage")))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# ── CORS ──────────────────────────────────────
CORS_ORIGINS: list[str] = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")

# ── Celery ────────────────────────────────────
CELERY_BROKER_URL:  str = os.getenv("CELERY_BROKER_URL",  "redis://localhost:6379/0")
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
