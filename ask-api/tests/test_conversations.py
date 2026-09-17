"""对话 API 接口测试

测试对话 CRUD 和消息接口。
"""

import pytest


class TestConversationCRUD:
    """对话增删改查测试"""

    @pytest.mark.asyncio
    async def test_create_conversation(self, client, activated_user):
        """创建新对话"""
        resp = await client.post("/api/conversations", json={
            "title": "查找大文件"
        }, headers={"X-Device-ID": "test-device-001"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "查找大文件"
        assert data["message_count"] == 0
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_conversation_no_title(self, client, activated_user):
        """不传标题，使用默认值"""
        resp = await client.post("/api/conversations", json={},
            headers={"X-Device-ID": "test-device-001"})
        assert resp.status_code == 201
        assert resp.json()["title"] == "新对话"

    @pytest.mark.asyncio
    async def test_list_conversations(self, client, activated_user):
        """获取对话列表"""
        # 创建 3 个对话
        for title in ["对话1", "对话2", "对话3"]:
            await client.post("/api/conversations", json={"title": title},
                headers={"X-Device-ID": "test-device-001"})

        resp = await client.get("/api/conversations",
            headers={"X-Device-ID": "test-device-001"})
        assert resp.status_code == 200
        convs = resp.json()
        assert len(convs) == 3

    @pytest.mark.asyncio
    async def test_delete_conversation(self, client, activated_user):
        """删除对话"""
        # 创建
        resp = await client.post("/api/conversations", json={"title": "待删除"},
            headers={"X-Device-ID": "test-device-001"})
        conv_id = resp.json()["id"]

        # 删除
        del_resp = await client.delete(
            f"/api/conversations/{conv_id}",
            headers={"X-Device-ID": "test-device-001"})
        assert del_resp.status_code == 204

        # 确认删除后列表为空
        list_resp = await client.get("/api/conversations",
            headers={"X-Device-ID": "test-device-001"})
        assert len(list_resp.json()) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(self, client, activated_user):
        """删除不存在的对话"""
        resp = await client.delete(
            "/api/conversations/nonexistent-id",
            headers={"X-Device-ID": "test-device-001"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_conversations_require_auth(self, client):
        """未激活设备无法访问对话"""
        resp = await client.get("/api/conversations",
            headers={"X-Device-ID": "unregistered-device"})
        assert resp.status_code == 401


class TestMessages:
    """消息接口测试"""

    @pytest.mark.asyncio
    async def test_send_message(self, client, activated_user):
        """发送用户消息"""
        # 先创建对话
        conv_resp = await client.post("/api/conversations", json={"title": "测试"},
            headers={"X-Device-ID": "test-device-001"})
        conv_id = conv_resp.json()["id"]

        # 发送消息
        msg_resp = await client.post(
            f"/api/conversations/{conv_id}/messages",
            json={"content": "怎么查找大于 1GB 的文件"},
            headers={"X-Device-ID": "test-device-001"})
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert data["role"] == "user"
        assert data["content"] == "怎么查找大于 1GB 的文件"
        assert data["danger_level"] == "safe"
        assert data["command"] is None

    @pytest.mark.asyncio
    async def test_send_empty_message(self, client, activated_user):
        """发送空消息被拒"""
        conv_resp = await client.post("/api/conversations", json={},
            headers={"X-Device-ID": "test-device-001"})
        conv_id = conv_resp.json()["id"]

        resp = await client.post(
            f"/api/conversations/{conv_id}/messages",
            json={"content": ""},
            headers={"X-Device-ID": "test-device-001"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_messages(self, client, activated_user):
        """获取对话消息列表"""
        conv_resp = await client.post("/api/conversations", json={},
            headers={"X-Device-ID": "test-device-001"})
        conv_id = conv_resp.json()["id"]

        # 发送 3 条消息
        for i in range(3):
            await client.post(
                f"/api/conversations/{conv_id}/messages",
                json={"content": f"消息{i}"},
                headers={"X-Device-ID": "test-device-001"})

        resp = await client.get(
            f"/api/conversations/{conv_id}/messages",
            headers={"X-Device-ID": "test-device-001"})
        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) == 3
        assert messages[0]["content"] == "消息0"
        assert messages[2]["content"] == "消息2"

    @pytest.mark.asyncio
    async def test_messages_for_nonexistent_conversation(self, client, activated_user):
        """获取不存在对话的消息"""
        resp = await client.get(
            "/api/conversations/fake-id/messages",
            headers={"X-Device-ID": "test-device-001"})
        assert resp.status_code == 404


class TestHealthCheck:
    """健康检查测试"""

    @pytest.mark.asyncio
    async def test_health(self, client):
        """健康检查"""
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"
        assert "version" in data
