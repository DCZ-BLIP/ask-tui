"""邀请码服务单元测试

测试邀请码生成、验证、激活逻辑。
"""

import pytest
import pytest_asyncio
from app.services.invite_service import (
    generate_invite_code,
    create_invite_codes,
    validate_invite_code,
    activate_user,
    get_user_by_device,
)
from app.models import InviteCode


class TestGenerateInviteCode:
    """邀请码生成测试"""

    def test_format(self):
        code = generate_invite_code()
        # 格式：ASK-XXXX-XXX
        assert code.startswith("ASK-")
        parts = code.split("-")
        assert len(parts) == 3
        assert parts[0] == "ASK"
        assert len(parts[1]) == 4
        assert len(parts[2]) == 3

    def test_uniqueness(self):
        """生成 100 个码不重复"""
        codes = {generate_invite_code() for _ in range(100)}
        assert len(codes) == 100

    def test_charset(self):
        """只包含大写字母和数字"""
        import string
        valid_chars = set(string.ascii_uppercase + string.digits + "-")
        for _ in range(50):
            code = generate_invite_code()
            for ch in code:
                assert ch in valid_chars


class TestValidateInviteCode:
    """邀请码验证测试"""

    @pytest.mark.asyncio
    async def test_valid_code(self, db):
        codes = await create_invite_codes(db, count=1)
        code_str = codes[0].code
        result = await validate_invite_code(db, code_str)
        assert result is not None
        assert result.code == code_str

    @pytest.mark.asyncio
    async def test_invalid_code(self, db):
        result = await validate_invite_code(db, "ASK-WRONG-CODE")
        assert result is None

    @pytest.mark.asyncio
    async def test_used_code(self, db):
        codes = await create_invite_codes(db, count=1)
        code = codes[0]
        code.is_used = True
        await db.flush()
        result = await validate_invite_code(db, code.code)
        assert result is None

    @pytest.mark.asyncio
    async def test_case_insensitive(self, db):
        codes = await create_invite_codes(db, count=1)
        code_str = codes[0].code.lower()
        # validate 内部做了 upper() 处理
        result = await validate_invite_code(db, code_str)
        assert result is not None


class TestActivateUser:
    """用户激活测试"""

    @pytest.mark.asyncio
    async def test_activate_success(self, db):
        codes = await create_invite_codes(db, count=1)
        user = await activate_user(
            db, codes[0].code, "小明", "device-001"
        )
        assert user.username == "小明"
        assert user.device_id == "device-001"
        assert user.is_active is True

        # 邀请码标记为已使用
        await db.refresh(codes[0])
        assert codes[0].is_used is True
        assert codes[0].used_at is not None

    @pytest.mark.asyncio
    async def test_activate_with_invalid_code(self, db):
        with pytest.raises(ValueError, match="邀请码无效"):
            await activate_user(db, "ASK-FAKE-CODE", "小明", "device-001")

    @pytest.mark.asyncio
    async def test_activate_duplicate_device(self, db):
        codes = await create_invite_codes(db, count=2)
        # 先激活一次
        await activate_user(db, codes[0].code, "小明", "device-001")
        # 同设备再激活（用不同邀请码）
        with pytest.raises(ValueError, match="该设备已激活"):
            await activate_user(db, codes[1].code, "小红", "device-001")

    @pytest.mark.asyncio
    async def test_activate_used_code(self, db):
        codes = await create_invite_codes(db, count=1)
        # 先激活
        await activate_user(db, codes[0].code, "小明", "device-001")
        # 再用同一邀请码激活另一个设备
        with pytest.raises(ValueError, match="邀请码无效"):
            await activate_user(db, codes[0].code, "小红", "device-002")

    @pytest.mark.asyncio
    async def test_get_user_by_device(self, db):
        codes = await create_invite_codes(db, count=1)
        await activate_user(db, codes[0].code, "小明", "device-001")
        user = await get_user_by_device(db, "device-001")
        assert user is not None
        assert user.username == "小明"

    @pytest.mark.asyncio
    async def test_get_user_by_device_not_found(self, db):
        user = await get_user_by_device(db, "nonexistent-device")
        assert user is None
