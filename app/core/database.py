"""数据库连接管理（SQLAlchemy 2.0 异步风格）。"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.config import settings

_connect_args: dict = {}
_engine_kwargs: dict = {"pool_pre_ping": True, "echo": settings.DEBUG}

# SQLite 特殊处理：内存库（测试）需共享单个连接
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
    if ":memory:" in settings.DATABASE_URL:
        _engine_kwargs["poolclass"] = StaticPool

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    **_engine_kwargs,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


async def get_db():
    """FastAPI 依赖：为每个请求提供独立数据库会话。"""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """开发/测试用：直接根据元数据建表（生产建议使用 Alembic 迁移）。"""
    from app import models  # noqa: F401  确保模型已注册到元数据

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
