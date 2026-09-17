"""健康检查路由"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """健康检查接口

    检查服务是否正常运行，数据库是否可连接。
    """
    try:
        # 测试数据库连接
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "service": "ask-api",
        "version": "0.1.0",
        "database": db_status,
    }
