"""数据模型单元测试

测试模型字段、默认值、约束。
注意：SQLAlchemy 的 mapped_column(default=...) 在 flush 时才应用，
所以测试默认值时需要先 flush。
"""

import pytest
import pytest_asyncio
from app.models import User, InviteCode, Conversation, Message
from sqlalchemy.ext.asyncio import AsyncSession


class TestInviteCode:
    """邀请码模型测试"""

    @pytest.mark.asyncio
    async def test_default_values(self, db):
        """flush 后检查默认值"""
        code = InviteCode(code="ASK-TEST-001")
        db.add(code)
        await db.flush()
        assert code.code == "ASK-TEST-001"
        assert code.is_used is False
        assert code.used_at is None

    def test_repr(self):
        code = InviteCode(code="ASK-TEST-001")
        assert "ASK-TEST-001" in repr(code)


class TestUser:
    """用户模型测试"""

    @pytest.mark.asyncio
    async def test_uuid_generation(self, db):
        """flush 后检查 UUID 是否生成"""
        # 先创建邀请码
        invite = InviteCode(code="ASK-UUID-001")
        db.add(invite)
        await db.flush()

        user1 = User(username="user1", device_id="dev1", invite_code_id=invite.id)
        user2 = User(username="user2", device_id="dev2", invite_code_id=invite.id)
        # 邀请码 1:1 用户，改用不同邀请码
        invite2 = InviteCode(code="ASK-UUID-002")
        db.add(invite2)
        await db.flush()
        user2.invite_code_id = invite2.id

        db.add(user1)
        db.add(user2)
        await db.flush()
        assert user1.id != user2.id
        assert len(user1.id) == 32  # uuid4 hex

    @pytest.mark.asyncio
    async def test_default_values(self, db):
        invite = InviteCode(code="ASK-DEF-001")
        db.add(invite)
        await db.flush()

        user = User(username="test", device_id="dev1", invite_code_id=invite.id)
        db.add(user)
        await db.flush()
        assert user.username == "test"
        assert user.is_active is True


class TestConversation:
    """对话模型测试"""

    @pytest.mark.asyncio
    async def test_default_title(self, db):
        """flush 后检查默认标题"""
        # 需要 user_id，先创建邀请码和用户
        invite = InviteCode(code="ASK-CONV-001")
        db.add(invite)
        await db.flush()
        user = User(username="u", device_id="dev-conv", invite_code_id=invite.id)
        db.add(user)
        await db.flush()

        conv = Conversation(user_id=user.id)
        db.add(conv)
        await db.flush()
        assert conv.title == "新对话"

    def test_custom_title(self):
        conv = Conversation(user_id="fake", title="查找文件")
        assert conv.title == "查找文件"


class TestMessage:
    """消息模型测试"""

    @pytest.mark.asyncio
    async def test_user_message(self, db):
        """flush 后检查默认值"""
        # 创建完整依赖链
        invite = InviteCode(code="ASK-MSG-001")
        db.add(invite)
        await db.flush()
        user = User(username="u", device_id="dev-msg", invite_code_id=invite.id)
        db.add(user)
        await db.flush()
        conv = Conversation(user_id=user.id)
        db.add(conv)
        await db.flush()

        msg = Message(conversation_id=conv.id, role="user", content="你好")
        db.add(msg)
        await db.flush()
        assert msg.role == "user"
        assert msg.content == "你好"
        assert msg.command is None
        assert msg.explanation is None
        assert msg.danger_level == "safe"

    def test_ai_message_with_command(self):
        """不需要 flush，显式设置了所有字段"""
        msg = Message(
            conversation_id="fake-conv",
            role="assistant",
            content="这是命令",
            command="dir *.txt",
            explanation="列出所有 txt 文件",
            danger_level="safe",
        )
        assert msg.role == "assistant"
        assert msg.command == "dir *.txt"
        assert msg.danger_level == "safe"

    def test_danger_message(self):
        msg = Message(
            conversation_id="fake-conv",
            role="assistant",
            content="危险操作",
            command="rm -rf /",
            danger_level="danger",
        )
        assert msg.danger_level == "danger"
