"""管理员鉴权依赖

通过 X-Admin-Key 头校验管理员身份。
"""

from fastapi import Header, HTTPException

from app.config import settings


async def require_admin(x_admin_key: str = Header(...)) -> str:
    """管理员鉴权依赖

    在路由中通过 dependencies=[Depends(require_admin)] 使用。
    """
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="管理员密钥无效")
    return x_admin_key
