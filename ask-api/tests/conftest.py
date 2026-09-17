"""测试公共 fixtures

提供测试数据库、测试客户端等基础设施。
关键：内存 SQLite 默认每个连接独立，需要 StaticPool 共享连接。
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app
from app.config import settings
from app.services.invite_service import create_invite_codes
from app.middleware.rate_limit import reset_rate_store
import app.routers.chat as chat_module


# ===== 测试数据库引擎（内存 SQLite + StaticPool）=====
# StaticPool 让所有 session 共享同一个连接，解决内存 SQLite
# 不同连接看到不同数据库的问题
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """每个测试前创建表、重置限流计数器，测试后删除"""
    reset_rate_store()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    """测试用数据库会话（直接操作数据库，用于单元测试）"""
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client():
    """测试用 HTTP 客户端

    自动替换数据库依赖为测试数据库。
    每个请求使用独立的 session，用完自动 commit。
    """
    async def get_test_db():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    # 替换依赖
    app.dependency_overrides[get_db] = get_test_db

    # 替换 chat 路由中的 async_session（SSE 流内部用，无法走 DI）
    original_session = chat_module.async_session
    chat_module.async_session = test_session_factory

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    chat_module.async_session = original_session


@pytest_asyncio.fixture
async def invite_code(db):
    """创建一个测试邀请码，返回码字符串"""
    codes = await create_invite_codes(db, count=1)
    await db.commit()
    return codes[0].code


@pytest_asyncio.fixture
async def activated_user(client, invite_code):
    """激活一个测试用户，返回用户信息"""
    resp = await client.post("/api/auth/activate", json={
        "invite_code": invite_code,
        "username": "测试用户",
        "device_id": "test-device-001",
    })
    assert resp.status_code == 200
    return resp.json()


@pytest.fixture
def admin_headers():
    """管理员请求头"""
    return {"X-Admin-Key": settings.ADMIN_API_KEY}
