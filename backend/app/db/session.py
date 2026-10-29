"""数据库会话与引擎。

平台只允许操作 `veeam_inspection` 库，配置校验已在 Settings 层强制。
"""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.sqlalchemy_url_object,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> None:
    """启动时校验数据库连通性，连不上直接失败（避免带着坏连接启动）。"""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def get_database_info() -> dict:
    """返回当前连接的库信息，用于系统状态接口。"""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT DATABASE() AS db, VERSION() AS version")
        ).mappings().first()
    return dict(row or {})
