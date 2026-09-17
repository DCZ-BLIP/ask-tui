"""数据库模型定义

4 张表：
  1. users          - 用户表
  2. invite_codes   - 邀请码表
  3. conversations  - 对话表
  4. messages       - 消息表

关系：
  invite_codes 1:1 users     （一个邀请码激活一个用户）
  users 1:N conversations     （一个用户有多个对话）
  conversations 1:N messages  （一个对话有多条消息）
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database import Base


def _uuid() -> str:
    """生成 UUID 字符串（去掉横杠，更短）"""
    return uuid.uuid4().hex


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    invite_code_id: Mapped[str] = mapped_column(
        ForeignKey("invite_codes.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 关系
    invite_code: Mapped["InviteCode"] = relationship(back_populates="user")
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.id[:8]} {self.username}>"


class InviteCode(Base):
    """邀请码表

    管理员预先生成邀请码，用户用邀请码激活账号。
    """

    __tablename__ = "invite_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 关系
    user: Mapped["User | None"] = relationship(back_populates="invite_code", uselist=False)

    def __repr__(self):
        status = "已使用" if self.is_used else "未使用"
        return f"<InviteCode {self.code} [{status}]>"


class Conversation(Base):
    """对话表

    每次新对话创建一条记录，用户可以在多个对话间切换。
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False, default="新对话")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Conversation {self.id[:8]} {self.title}>"


class Message(Base):
    """消息表

    每条消息记录角色（用户/AI）、内容、AI 生成的命令等信息。
    数据回收定时任务根据 created_at 清理超过保留天期的消息。
    """

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # AI 返回的命令（仅 assistant 消息有）
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 命令解释（仅 assistant 消息有）
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 危险等级：safe / warn / danger
    danger_level: Mapped[str] = mapped_column(String(10), default="safe")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # 关系
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def __repr__(self):
        return f"<Message {self.id[:8]} [{self.role}]>"
