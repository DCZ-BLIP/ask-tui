"""对话路由

对话和消息的增删改查。
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import (
    CreateConversationRequest,
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
)
from app.services.conversation_service import (
    create_conversation,
    get_conversations_by_user,
    get_conversation_by_id,
    delete_conversation,
    add_message,
    get_messages_by_conversation,
)
from app.services.invite_service import get_user_by_device

router = APIRouter()


async def _get_user_id(db: AsyncSession, device_id: str) -> str:
    """通过设备 ID 获取用户 ID，不存在则报错"""
    user = await get_user_by_device(db, device_id)
    if user is None:
        raise HTTPException(status_code=401, detail="设备未激活，请先激活")
    return user.id


# ===== 对话 CRUD =====

@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    x_device_id: str = Header(...),
) -> list[dict]:
    """获取当前用户的所有对话"""
    user_id = await _get_user_id(db, x_device_id)
    return await get_conversations_by_user(db, user_id)


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conv(
    req: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    x_device_id: str = Header(...),
) -> dict:
    """创建新对话"""
    user_id = await _get_user_id(db, x_device_id)
    conv = await create_conversation(db, user_id, req.title)
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "message_count": 0,
    }


@router.delete("/{conv_id}", status_code=204)
async def delete_conv(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
    x_device_id: str = Header(...),
):
    """删除对话（级联删除消息）"""
    user_id = await _get_user_id(db, x_device_id)
    conv = await get_conversation_by_id(db, conv_id, user_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    await delete_conversation(db, conv_id)
    return None


# ===== 消息 =====

@router.get("/{conv_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
    x_device_id: str = Header(...),
) -> list[MessageResponse]:
    """获取某个对话的所有消息"""
    user_id = await _get_user_id(db, x_device_id)
    conv = await get_conversation_by_id(db, conv_id, user_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    messages = await get_messages_by_conversation(db, conv_id)
    return [MessageResponse.model_validate(m) for m in messages]


@router.post("/{conv_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    conv_id: str,
    req: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    x_device_id: str = Header(...),
) -> MessageResponse:
    """发送用户消息

    注意：这个接口只保存用户消息到数据库。
    AI 回复将在第 2 阶段通过 /api/chat 流式接口实现。
    """
    user_id = await _get_user_id(db, x_device_id)
    conv = await get_conversation_by_id(db, conv_id, user_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    msg = await add_message(
        db,
        conversation_id=conv_id,
        role="user",
        content=req.content,
    )
    return MessageResponse.model_validate(msg)
