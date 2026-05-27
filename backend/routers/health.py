"""
routers/health.py — 服务健康检查，兼作配置核验
"""
from fastapi import APIRouter
from ..core.config import MINIMAX_API_KEY, MOONSHOT_API_KEY

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {
        "status": "ok",
        "minimax_key_set": bool(MINIMAX_API_KEY),
        "moonshot_key_set": bool(MOONSHOT_API_KEY),
    }
