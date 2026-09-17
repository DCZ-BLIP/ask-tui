"""聊天 API 接口测试

测试流式 AI 对话接口（需 mock AI 服务）。
"""

import json
from unittest.mock import patch
import pytest


# ===== Mock AI 流式响应 =====

async def mock_ai_stream(messages):
    """模拟 AI 流式响应 — 返回完整 JSON 分两块"""
    full = json.dumps({
        "thinking": "查找大文件",
        "command": "find . -type f -size +1G",
        "explanation": "find 命令查找当前目录下大于 1G 的文件",
        "danger_level": "safe",
    }, ensure_ascii=False)
    mid = len(full) // 2
    yield full[:mid]
    yield full[mid:]


async def mock_ai_stream_dangerous(messages):
    """模拟危险命令"""
    full = json.dumps({
        "thinking": "递归删除",
        "command": "rm -rf /tmp/test",
        "explanation": "递归删除目录，不可恢复",
        "danger_level": "danger",
    }, ensure_ascii=False)
    yield full


async def mock_ai_stream_error(messages):
    """模拟 AI 返回非 JSON"""
    yield "抱歉，我无法理解这个请求"


# ===== 辅助函数 =====

def parse_sse(response_text: str) -> list[dict]:
    """解析 SSE 响应文本为事件列表"""
    events = []
    for line in response_text.strip().split("\n"):
        if line.startswith("data: "):
            data = line[6:]
            try:
                events.append(json.loads(data))
            except json.JSONDecodeError:
                pass
    return events


# ===== 测试 =====

class TestChat:
    """聊天接口测试"""

    @pytest.mark.asyncio
    async def test_chat_success(self, client, activated_user):
        """成功聊天 — 验证 SSE 事件流"""
        # 创建对话
        conv_resp = await client.post("/api/conversations", json={"title": "测试"},
            headers={"X-Device-ID": "test-device-001"})
        conv_id = conv_resp.json()["id"]

        with patch("app.routers.chat.chat_completion_stream", mock_ai_stream):
            resp = await client.post("/api/chat", json={
                "conversation_id": conv_id,
                "content": "怎么查找大于1GB的文件",
            }, headers={"X-Device-ID": "test-device-001"})

        assert resp.status_code == 200
        events = parse_sse(resp.text)

        # 验证事件序列
        types = [e["type"] for e in events]
        assert types[0] == "start"
        assert "chunk" in types
        assert "result" in types
        assert types[-1] == "done"

        # 验证结果结构
        result = next(e for e in events if e["type"] == "result")
        assert result["command"] == "find . -type f -size +1G"
        assert result["danger_level"] == "safe"
        assert result["thinking"] == "查找大文件"
        assert "message_id" in result

    @pytest.mark.asyncio
    async def test_chat_dangerous_command(self, client, activated_user):
        """危险命令 — danger_level 正确传递"""
        conv_resp = await client.post("/api/conversations", json={},
            headers={"X-Device-ID": "test-device-001"})
        conv_id = conv_resp.json()["id"]

        with patch("app.routers.chat.chat_completion_stream", mock_ai_stream_dangerous):
            resp = await client.post("/api/chat", json={
                "conversation_id": conv_id,
                "content": "删除测试目录",
            }, headers={"X-Device-ID": "test-device-001"})

        assert resp.status_code == 200
        events = parse_sse(resp.text)
        result = next(e for e in events if e["type"] == "result")
        assert result["danger_level"] == "danger"
        assert "rm -rf" in result["command"]

    @pytest.mark.asyncio
    async def test_chat_nonexistent_conversation(self, client, activated_user):
        """对话不存在"""
        with patch("app.routers.chat.chat_completion_stream", mock_ai_stream):
            resp = await client.post("/api/chat", json={
                "conversation_id": "nonexistent-id",
                "content": "测试",
            }, headers={"X-Device-ID": "test-device-001"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chat_requires_auth(self, client):
        """未激活设备"""
        resp = await client.post("/api/chat", json={
            "conversation_id": "any",
            "content": "test",
        }, headers={"X-Device-ID": "unregistered"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_empty_content(self, client, activated_user):
        """空消息被拒"""
        conv_resp = await client.post("/api/conversations", json={},
            headers={"X-Device-ID": "test-device-001"})
        conv_id = conv_resp.json()["id"]

        resp = await client.post("/api/chat", json={
            "conversation_id": conv_id,
            "content": "",
        }, headers={"X-Device-ID": "test-device-001"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_saves_messages(self, client, activated_user):
        """验证用户和 AI 消息都保存到数据库"""
        conv_resp = await client.post("/api/conversations", json={},
            headers={"X-Device-ID": "test-device-001"})
        conv_id = conv_resp.json()["id"]

        with patch("app.routers.chat.chat_completion_stream", mock_ai_stream):
            await client.post("/api/chat", json={
                "conversation_id": conv_id,
                "content": "测试消息",
            }, headers={"X-Device-ID": "test-device-001"})

        # 查看消息列表
        msg_resp = await client.get(
            f"/api/conversations/{conv_id}/messages",
            headers={"X-Device-ID": "test-device-001"})
        assert msg_resp.status_code == 200
        messages = msg_resp.json()
        assert len(messages) == 2  # user + assistant
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "测试消息"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["command"] == "find . -type f -size +1G"
        assert messages[1]["danger_level"] == "safe"

    @pytest.mark.asyncio
    async def test_chat_invalid_json_fallback(self, client, activated_user):
        """AI 返回非 JSON — 降级处理"""
        conv_resp = await client.post("/api/conversations", json={},
            headers={"X-Device-ID": "test-device-001"})
        conv_id = conv_resp.json()["id"]

        with patch("app.routers.chat.chat_completion_stream", mock_ai_stream_error):
            resp = await client.post("/api/chat", json={
                "conversation_id": conv_id,
                "content": "无法理解的需求",
            }, headers={"X-Device-ID": "test-device-001"})

        assert resp.status_code == 200
        events = parse_sse(resp.text)
        result = next(e for e in events if e["type"] == "result")
        assert result["command"] == ""  # 无法解析，命令为空
        assert result["danger_level"] == "safe"  # 默认安全

    @pytest.mark.asyncio
    async def test_chat_context_preserved(self, client, activated_user):
        """多轮对话上下文 — AI 收到历史消息"""
        conv_resp = await client.post("/api/conversations", json={},
            headers={"X-Device-ID": "test-device-001"})
        conv_id = conv_resp.json()["id"]

        # 捕获 AI 收到的 messages
        received_messages = []

        async def mock_with_capture(messages):
            received_messages.extend(messages)
            full = json.dumps({
                "thinking": "回复",
                "command": "echo hello",
                "explanation": "打印",
                "danger_level": "safe",
            }, ensure_ascii=False)
            yield full

        # 第一轮
        with patch("app.routers.chat.chat_completion_stream", mock_with_capture):
            await client.post("/api/chat", json={
                "conversation_id": conv_id,
                "content": "第一句话",
            }, headers={"X-Device-ID": "test-device-001"})

        received_messages.clear()

        # 第二轮
        with patch("app.routers.chat.chat_completion_stream", mock_with_capture):
            await client.post("/api/chat", json={
                "conversation_id": conv_id,
                "content": "第二句话",
            }, headers={"X-Device-ID": "test-device-001"})

        # 验证上下文包含 system + 第一轮 user + 第一轮 assistant + 第二轮 user
        roles = [m["role"] for m in received_messages]
        assert roles[0] == "system"
        assert "user" in roles
        assert "assistant" in roles
        assert roles[-1] == "user"


class TestRateLimit:
    """聊天接口限流测试"""

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, client, activated_user, monkeypatch):
        """超过每日请求限制返回 429"""
        # 将限制设为 2 次
        from app.middleware import rate_limit as rl
        monkeypatch.setattr(rl.settings, "DAILY_REQUEST_LIMIT", 2)
        rl.reset_rate_store()

        conv_resp = await client.post("/api/conversations", json={},
            headers={"X-Device-ID": "test-device-001"})
        conv_id = conv_resp.json()["id"]

        with patch("app.routers.chat.chat_completion_stream", mock_ai_stream):
            # 第一次
            resp1 = await client.post("/api/chat", json={
                "conversation_id": conv_id, "content": "1",
            }, headers={"X-Device-ID": "test-device-001"})
            assert resp1.status_code == 200

            # 第二次
            resp2 = await client.post("/api/chat", json={
                "conversation_id": conv_id, "content": "2",
            }, headers={"X-Device-ID": "test-device-001"})
            assert resp2.status_code == 200

            # 第三次 — 超限
            resp3 = await client.post("/api/chat", json={
                "conversation_id": conv_id, "content": "3",
            }, headers={"X-Device-ID": "test-device-001"})
            assert resp3.status_code == 429
            assert "上限" in resp3.json()["detail"]
