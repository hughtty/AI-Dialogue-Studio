"""
core/database.py — SQLAlchemy 数据库连接
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import DATABASE_URL

# SQLite 需要 check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    """FastAPI 依赖注入用的数据库 Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """创建所有表（开发环境用，生产用 Alembic）"""
    from ..models import project, line, video_job  # noqa: 触发模型注册
    Base.metadata.create_all(bind=engine)
