"""邀请码服务

负责邀请码的生成、验证、激活逻辑。
"""

import secrets
import string
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import InviteCode, User
from datetime import datetime, timezone


def generate_invite_code() -> str:
    """生成邀请码，格式：ASK-XXXX-XXX

    示例：ASK-7K3M-9ZQ
    """
    chars = string.ascii_uppercase + string.digits
    part1 = "".join(secrets.choice(chars) for _ in range(4))
    part2 = "".join(secrets.choice(chars) for _ in range(3))
    return f"ASK-{part1}-{part2}"


async def create_invite_codes(db: AsyncSession, count: int = 1) -> list[InviteCode]:
    """批量生成邀请码

    Args:
        db: 数据库会话
        count: 生成数量

    Returns:
        生成的邀请码列表
    """
    codes = []
    for _ in range(count):
        # 确保不重复（概率极低，但防御性处理）
        while True:
            code_str = generate_invite_code()
            existing = await db.execute(
                select(InviteCode).where(InviteCode.code == code_str)
            )
            if existing.scalar_one_or_none() is None:
                break

        invite = InviteCode(code=code_str, is_used=False)
        db.add(invite)
        codes.append(invite)

    await db.flush()
    return codes


async def validate_invite_code(db: AsyncSession, code: str) -> InviteCode | None:
    """验证邀请码是否有效

    Args:
        db: 数据库会话
        code: 邀请码字符串

    Returns:
        邀请码对象（有效）或 None（无效/已使用）
    """
    result = await db.execute(
        select(InviteCode).where(
            InviteCode.code == code.upper().strip(),
            InviteCode.is_used == False,
        )
    )
    return result.scalar_one_or_none()


async def activate_user(
    db: AsyncSession, invite_code: str, username: str, device_id: str
) -> User:
    """用邀请码激活新用户

    Args:
        db: 数据库会话
        invite_code: 邀请码
        username: 昵称
        device_id: 设备 ID

    Returns:
        新创建的用户对象

    Raises:
        ValueError: 邀请码无效或已被使用
    """
    # 验证邀请码
    invite = await validate_invite_code(db, invite_code)
    if invite is None:
        raise ValueError("邀请码无效或已被使用")

    # 检查设备是否已激活（同一设备不重复激活）
    existing = await db.execute(
        select(User).where(User.device_id == device_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("该设备已激活，无需重复激活")

    # 创建用户
    user = User(
        username=username.strip(),
        device_id=device_id,
        invite_code_id=invite.id,
        is_active=True,
    )
    db.add(user)

    # 标记邀请码已使用
    invite.is_used = True
    invite.used_at = datetime.now(timezone.utc)

    await db.flush()
    return user


async def get_user_by_device(db: AsyncSession, device_id: str) -> User | None:
    """根据设备 ID 查询用户"""
    result = await db.execute(
        select(User).where(User.device_id == device_id)
    )
    return result.scalar_one_or_none()


async def get_all_invite_codes(db: AsyncSession) -> list[InviteCode]:
    """获取所有邀请码列表"""
    result = await db.execute(
        select(InviteCode).order_by(InviteCode.created_at.desc())
    )
    return list(result.scalars().all())
