"""消息清理定时任务

后台 asyncio 任务，定期清理过期消息。
"""

import asyncio

from app.config import settings
from app.database import async_session
from app.services.conversation_service import cleanup_old_messages


async def cleanup_scheduler():
    """定期清理过期消息的后台任务

    每 CLEANUP_INTERVAL_HOURS 小时执行一次，
    删除创建时间超过 MESSAGE_RETENTION_DAYS 天的消息。
    """
    # 启动后先等待一个周期再执行（避免启动时立即跑）
    interval = settings.CLEANUP_INTERVAL_HOURS * 3600

    while True:
        await asyncio.sleep(interval)
        try:
            async with async_session() as session:
                count = await cleanup_old_messages(session)
                await session.commit()
                if count > 0:
                    print(f"[cleanup] 删除了 {count} 条过期消息")
        except Exception as e:
            print(f"[cleanup] 错误: {e}")
