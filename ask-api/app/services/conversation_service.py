"""对话服务

负责对话和消息的增删改查。
"""

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Conversation, Message
from datetime import datetime, timezone, timedelta
from app.config import settings


async def create_conversation(
    db: AsyncSession, user_id: str, title: str | None = None
) -> Conversation:
    """创建新对话"""
    conv = Conversation(
        user_id=user_id,
        title=title or "新对话",
    )
    db.add(conv)
    await db.flush()
    return conv


async def get_conversations_by_user(
    db: AsyncSession, user_id: str
) -> list[dict]:
    """获取用户的所有对话列表（含消息数）"""
    # 查询对话 + 消息计数
    result = await db.execute(
        select(
            Conversation,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Conversation.id == Message.conversation_id)
        .where(Conversation.user_id == user_id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
    )
    rows = result.all()

    return [
        {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "message_count": msg_count,
        }
        for conv, msg_count in rows
    ]


async def get_conversation_by_id(
    db: AsyncSession, conv_id: str, user_id: str | None = None
) -> Conversation | None:
    """根据 ID 获取对话

    如果传入 user_id，则只返回属于该用户的对话。
    """
    stmt = select(Conversation).where(Conversation.id == conv_id)
    if user_id is not None:
        stmt = stmt.where(Conversation.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_conversation(db: AsyncSession, conv_id: str) -> bool:
    """删除对话（级联删除消息）"""
    result = await db.execute(
        delete(Conversation).where(Conversation.id == conv_id)
    )
    return result.rowcount > 0


async def add_message(
    db: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    command: str | None = None,
    explanation: str | None = None,
    danger_level: str = "safe",
) -> Message:
    """添加一条消息"""
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        command=command,
        explanation=explanation,
        danger_level=danger_level,
    )
    db.add(msg)

    # 更新对话的 updated_at
    conv = await db.get(Conversation, conversation_id)
    if conv:
        conv.updated_at = datetime.now(timezone.utc)

    await db.flush()
    return msg


async def get_messages_by_conversation(
    db: AsyncSession, conversation_id: str
) -> list[Message]:
    """获取对话的所有消息"""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())


async def cleanup_old_messages(db: AsyncSession) -> int:
    """清理过期消息

    删除创建时间超过 MESSAGE_RETENTION_DAYS 天的消息。

    Returns:
        删除的消息数量
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=settings.MESSAGE_RETENTION_DAYS
    )
    result = await db.execute(
        delete(Message).where(Message.created_at < cutoff)
    )
    return result.rowcount
