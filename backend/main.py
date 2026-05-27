"""
main.py — FastAPI 应用入口
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .core.config import CORS_ORIGINS, STORAGE_DIR
from .core.database import init_db
from .routers import projects, health, story, tts, video, screenshots

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Dialogue Studio API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

app.include_router(health.router)
app.include_router(projects.router, prefix="/api")
app.include_router(story.router, prefix="/api")
app.include_router(tts.router, prefix="/api")
app.include_router(video.router, prefix="/api")
app.include_router(screenshots.router, prefix="/api")

@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.on_event("startup")
def on_startup():
    init_db()
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    print("✓ 数据库初始化完成")
    print(f"✓ 文件存储目录：{STORAGE_DIR}")
    print("✓ 访问地址：http://localhost:8000")
