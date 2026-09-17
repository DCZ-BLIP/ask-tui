"""数据库配置模块

使用 SQLAlchemy 2.0 异步引擎。
支持 SQLite (开发) 和 PostgreSQL (生产) 两种后端。

Render 传入的 DATABASE_URL 格式为 postgresql://...
SQLAlchemy 异步需要 postgresql+asyncpg://...
此处自动转换协议。
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


def _normalize_db_url(url: str) -> str:
    """规范化数据库 URL

    - postgresql:// → postgresql+asyncpg://
    - postgres:// → postgresql+asyncpg://
    - sqlite:// → sqlite+aiosqlite://
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://") and "aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


db_url = _normalize_db_url(settings.DATABASE_URL)

# 异步引擎
is_postgres = "postgresql" in db_url

engine_kwargs = {
    "echo": settings.DEBUG,
}

if "sqlite" in db_url:
    # SQLite 需要这个参数避免多线程问题
    engine_kwargs["connect_args"] = {"check_same_thread": False}
elif is_postgres:
    # PostgreSQL 连接池配置
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(db_url, **engine_kwargs)

# 异步会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """所有模型类的基类"""
    pass


async def init_db():
    """初始化数据库：创建所有表

    在应用启动时调用（main.py 的 lifespan 中）。
    PostgreSQL 下使用 create_all 自动建表。
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """依赖注入：获取数据库会话

    在路由函数参数中使用 Depends(get_db) 自动注入。
    用完自动关闭。
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
