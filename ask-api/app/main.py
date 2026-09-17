"""FastAPI 应用入口

启动时自动创建数据库表。
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.routers import health, auth, conversations, chat
from app.middleware.rate_limit import rate_limit_middleware
from app.services.scheduler import cleanup_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库 + 启动定时清理任务"""
    await init_db()
    print(f"[{settings.APP_NAME}] 数据库初始化完成")
    # 启动消息清理后台任务
    cleanup_task = asyncio.create_task(cleanup_scheduler())
    print(f"[{settings.APP_NAME}] 消息清理任务已启动")
    yield
    cleanup_task.cancel()
    print(f"[{settings.APP_NAME}] 应用关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI 命令行助手后端服务",
    lifespan=lifespan,
)

# CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流中间件（只限 /api/chat）
app.middleware("http")(rate_limit_middleware)

# 注册路由
app.include_router(health.router, prefix="/api", tags=["健康检查"])
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(
    conversations.router, prefix="/api/conversations", tags=["对话"]
)
app.include_router(chat.router, prefix="/api/chat", tags=["AI 对话"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
