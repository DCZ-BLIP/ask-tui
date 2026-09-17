"""请求限流中间件

每个设备每天最多 DAILY_REQUEST_LIMIT 次请求（仅限 /api/chat）。
使用内存存储，重启后重置。
"""

from collections import defaultdict
from datetime import date

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings

# 内存存储：{device_id: {date_str: count}}
_rate_store: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


async def rate_limit_middleware(request: Request, call_next):
    """限流中间件 — 只限制 /api/chat 接口"""
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)

    path = request.url.path
    if path != "/api/chat":
        return await call_next(request)

    device_id = request.headers.get("X-Device-ID")
    if not device_id:
        return await call_next(request)

    today = date.today().isoformat()
    count = _rate_store[device_id][today]

    if count >= settings.DAILY_REQUEST_LIMIT:
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"今日请求已达上限（{settings.DAILY_REQUEST_LIMIT} 次）"
            },
        )

    _rate_store[device_id][today] += 1
    response = await call_next(request)
    return response


def reset_rate_store():
    """清空限流存储（测试用）"""
    _rate_store.clear()


def get_device_usage(device_id: str) -> int:
    """获取设备今日已用次数（测试用）"""
    today = date.today().isoformat()
    return _rate_store.get(device_id, {}).get(today, 0)
