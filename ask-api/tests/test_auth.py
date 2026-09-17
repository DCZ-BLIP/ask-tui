"""认证 API 接口测试

测试邀请码激活、用户信息获取、管理员鉴权等接口。
"""

import pytest


class TestActivate:
    """激活接口测试"""

    @pytest.mark.asyncio
    async def test_activate_success(self, client, invite_code):
        """正确邀请码激活成功"""
        resp = await client.post("/api/auth/activate", json={
            "invite_code": invite_code,
            "username": "测试用户",
            "device_id": "test-device-001",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        assert data["username"] == "测试用户"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_activate_invalid_code(self, client):
        """错误邀请码激活失败"""
        resp = await client.post("/api/auth/activate", json={
            "invite_code": "ASK-WRONG-CODE",
            "username": "测试用户",
            "device_id": "test-device-001",
        })
        assert resp.status_code == 400
        assert "邀请码" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_activate_empty_username(self, client, invite_code):
        """空昵称被拒绝"""
        resp = await client.post("/api/auth/activate", json={
            "invite_code": invite_code,
            "username": "",
            "device_id": "test-device-001",
        })
        assert resp.status_code == 422  # Pydantic 校验失败

    @pytest.mark.asyncio
    async def test_activate_duplicate_device(self, client, invite_code, admin_headers):
        """同设备重复激活被拒"""
        resp1 = await client.post("/api/auth/activate", json={
            "invite_code": invite_code,
            "username": "用户A",
            "device_id": "test-device-001",
        })
        assert resp1.status_code == 200

        # 需要创建另一个邀请码（管理员接口需鉴权）
        codes_resp = await client.post(
            "/api/auth/admin/invite-codes?count=1",
            headers=admin_headers,
        )
        new_code = codes_resp.json()["codes"][0]

        resp2 = await client.post("/api/auth/activate", json={
            "invite_code": new_code,
            "username": "用户B",
            "device_id": "test-device-001",  # 同设备
        })
        assert resp2.status_code == 400
        assert "已激活" in resp2.json()["detail"]

    @pytest.mark.asyncio
    async def test_activate_used_code(self, client, invite_code):
        """已使用的邀请码不能再激活"""
        resp1 = await client.post("/api/auth/activate", json={
            "invite_code": invite_code,
            "username": "用户A",
            "device_id": "device-001",
        })
        assert resp1.status_code == 200

        resp2 = await client.post("/api/auth/activate", json={
            "invite_code": invite_code,
            "username": "用户B",
            "device_id": "device-002",
        })
        assert resp2.status_code == 400


class TestGetCurrentUser:
    """获取用户信息接口测试"""

    @pytest.mark.asyncio
    async def test_get_user_success(self, client, activated_user):
        """正确设备 ID 获取用户信息"""
        resp = await client.get("/api/auth/me", headers={
            "X-Device-ID": "test-device-001",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "测试用户"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, client):
        """未激活设备获取用户信息"""
        resp = await client.get("/api/auth/me", headers={
            "X-Device-ID": "nonexistent-device",
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_user_missing_header(self, client):
        """缺少设备 ID Header"""
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 422


class TestAdminInviteCodes:
    """管理员邀请码接口测试"""

    @pytest.mark.asyncio
    async def test_generate_one_code(self, client, admin_headers):
        """生成 1 个邀请码"""
        resp = await client.post(
            "/api/auth/admin/invite-codes?count=1",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert len(data["codes"]) == 1
        assert data["codes"][0].startswith("ASK-")

    @pytest.mark.asyncio
    async def test_generate_multiple_codes(self, client, admin_headers):
        """生成多个邀请码"""
        resp = await client.post(
            "/api/auth/admin/invite-codes?count=5",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5
        assert len(data["codes"]) == 5
        # 确保不重复
        assert len(set(data["codes"])) == 5

    @pytest.mark.asyncio
    async def test_list_invite_codes(self, client, admin_headers):
        """查看邀请码列表"""
        await client.post(
            "/api/auth/admin/invite-codes?count=3",
            headers=admin_headers,
        )
        resp = await client.get(
            "/api/auth/admin/invite-codes",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        codes = resp.json()
        assert len(codes) == 3
        for c in codes:
            assert "id" in c
            assert "code" in c
            assert "is_used" in c
            assert "created_at" in c


class TestAdminAuth:
    """管理员鉴权测试"""

    @pytest.mark.asyncio
    async def test_admin_without_key(self, client):
        """缺少管理员密钥被拒"""
        resp = await client.post("/api/auth/admin/invite-codes?count=1")
        assert resp.status_code == 422  # 缺少 X-Admin-Key 头

    @pytest.mark.asyncio
    async def test_admin_wrong_key(self, client):
        """错误管理员密钥被拒"""
        resp = await client.post(
            "/api/auth/admin/invite-codes?count=1",
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert resp.status_code == 403
        assert "管理员密钥" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_list_without_key(self, client):
        """查看邀请码缺少管理员密钥"""
        resp = await client.get("/api/auth/admin/invite-codes")
        assert resp.status_code == 422
