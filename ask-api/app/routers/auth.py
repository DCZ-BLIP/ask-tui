"""认证路由

邀请码激活、用户信息查询。
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import ActivateRequest, UserResponse, ErrorResponse
from app.middleware.admin_auth import require_admin
from app.services.invite_service import (
    activate_user,
    get_user_by_device,
    create_invite_codes,
    get_all_invite_codes,
)

router = APIRouter()


@router.post("/activate", response_model=UserResponse)
async def activate(
    req: ActivateRequest, db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """用邀请码激活新用户

    - 用户输入邀请码 + 昵称 + 设备 ID
    - 邀请码验证通过后创建用户，标记邀请码已使用
    """
    try:
        user = await activate_user(
            db, req.invite_code, req.username, req.device_id
        )
        await db.flush()
        await db.refresh(user)
        return UserResponse(
            user_id=user.id,
            username=user.username,
            is_active=user.is_active,
            created_at=user.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    x_device_id: str = Header(..., description="设备 ID"),
) -> UserResponse:
    """获取当前用户信息

    前端通过 Header 中的 X-Device-ID 标识用户。
    """
    user = await get_user_by_device(db, x_device_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户未找到，请先激活")
    return UserResponse(
        user_id=user.id,
        username=user.username,
        is_active=user.is_active,
        created_at=user.created_at,
    )


# ===== 管理员接口 =====

@router.post("/admin/invite-codes", dependencies=[Depends(require_admin)])
async def generate_invites(
    count: int = 1,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """生成邀请码（管理员接口，需 X-Admin-Key）

    可在初始化数据库后调用此接口生成邀请码。
    """
    codes = await create_invite_codes(db, count=count)
    return {
        "count": len(codes),
        "codes": [c.code for c in codes],
    }


@router.get("/admin/invite-codes", dependencies=[Depends(require_admin)])
async def list_invite_codes(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """查看所有邀请码（管理员接口，需 X-Admin-Key）"""
    codes = await get_all_invite_codes(db)
    return [
        {
            "id": c.id,
            "code": c.code,
            "is_used": c.is_used,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in codes
    ]
