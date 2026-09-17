"""Pydantic 数据验证模型

定义 API 请求和响应的数据结构，自动校验输入。
"""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional


# ===== 请求模型 =====

class ActivateRequest(BaseModel):
    """激活请求"""
    invite_code: str = Field(..., min_length=1, max_length=20, description="邀请码")
    username: str = Field(..., min_length=1, max_length=50, description="昵称")
    device_id: str = Field(..., min_length=1, max_length=64, description="设备唯一标识")

    @field_validator("invite_code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """去除首尾空格，转大写"""
        return v.strip().upper()

    @field_validator("username")
    @classmethod
    def clean_name(cls, v: str) -> str:
        """去除首尾空格"""
        return v.strip()


class CreateConversationRequest(BaseModel):
    """创建对话请求"""
    title: Optional[str] = Field(None, max_length=100, description="对话标题（可选）")


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    content: str = Field(..., min_length=1, max_length=2000, description="用户消息内容")


class GenerateInviteRequest(BaseModel):
    """生成邀请码请求（管理员用）"""
    count: int = Field(default=1, ge=1, le=100, description="生成数量 1-100")


class ChatRequest(BaseModel):
    """聊天请求（流式 AI 对话）"""
    conversation_id: str = Field(..., min_length=1, description="对话 ID")
    content: str = Field(..., min_length=1, max_length=2000, description="用户消息内容")


# ===== 响应模型 =====

class UserResponse(BaseModel):
    """用户信息响应"""
    user_id: str
    username: str
    is_active: bool
    created_at: datetime


class ConversationResponse(BaseModel):
    """对话信息响应"""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """消息信息响应"""
    id: str
    role: str
    content: str
    command: Optional[str] = None
    explanation: Optional[str] = None
    danger_level: str = "safe"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InviteCodeResponse(BaseModel):
    """邀请码响应"""
    id: str
    code: str
    is_used: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str
    code: str = "ERROR"
