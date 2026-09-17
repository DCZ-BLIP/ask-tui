"""聊天路由 — 流式 AI 对话

通过 SSE (Server-Sent Events) 流式返回 AI 生成的 shell 命令。
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.schemas import ChatRequest
from app.services.conversation_service import (
    get_conversation_by_id,
    add_message,
    get_messages_by_conversation,
)
from app.services.invite_service import get_user_by_device
from app.services.ai_service import (
    SYSTEM_PROMPT,
    chat_completion_stream,
    parse_ai_response,
)

router = APIRouter()


async def _get_user_id(db: AsyncSession, device_id: str) -> str:
    """通过设备 ID 获取用户 ID，不存在则报错"""
    user = await get_user_by_device(db, device_id)
    if user is None:
        raise HTTPException(status_code=401, detail="设备未激活，请先激活")
    return user.id


@router.post("")
async def chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    x_device_id: str = Header(...),
):
    """流式 AI 对话

    接收用户消息，调用 GLM-4-Flash 生成 shell 命令，
    通过 SSE 流式返回。

    SSE 事件格式：
    - {"type": "start", "user_message_id": "..."}
    - {"type": "chunk", "content": "..."}  （多次）
    - {"type": "result", "message_id": "...", "command": "...", ...}
    - {"type": "error", "detail": "..."}
    - {"type": "done"}
    """
    user_id = await _get_user_id(db, x_device_id)

    # 验证对话存在且属于该用户
    conv = await get_conversation_by_id(db, req.conversation_id, user_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    # 保存用户消息
    user_msg = await add_message(
        db,
        conversation_id=req.conversation_id,
        role="user",
        content=req.content,
    )
    await db.commit()

    # 获取对话历史，构建上下文
    history = await get_messages_by_conversation(db, req.conversation_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        if msg.role == "user":
            messages.append({"role": "user", "content": msg.content})
        else:
            # assistant 消息：用原始 content（JSON 字符串）
            messages.append({"role": "assistant", "content": msg.content})

    async def event_stream():
        """SSE 事件流"""
        full_response = ""
        try:
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'user_message_id': user_msg.id}, ensure_ascii=False)}\n\n"

            # 流式获取 AI 响应
            async for chunk in chat_completion_stream(messages):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

            # 解析 AI 响应为结构化数据
            parsed = parse_ai_response(full_response)

            # 用独立 session 保存 AI 消息（避免与请求 session 冲突）
            async with async_session() as session:
                ai_msg = await add_message(
                    session,
                    conversation_id=req.conversation_id,
                    role="assistant",
                    content=full_response,
                    command=parsed["command"],
                    explanation=parsed["explanation"],
                    danger_level=parsed["danger_level"],
                )
                await session.commit()
                ai_msg_id = ai_msg.id

            # 发送结构化结果
            result = {
                "type": "result",
                "message_id": ai_msg_id,
                "thinking": parsed["thinking"],
                "command": parsed["command"],
                "explanation": parsed["explanation"],
                "danger_level": parsed["danger_level"],
            }
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)}, ensure_ascii=False)}\n\n"

        # 发送结束事件
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
