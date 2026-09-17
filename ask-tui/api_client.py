"""API 客户端

封装与 ask-api 后端的所有 HTTP 交互，包括 SSE 流式聊天。
"""

import json
from typing import AsyncGenerator

import httpx


class ApiClient:
    """后端 API 客户端"""

    def __init__(self, base_url: str, device_id: str):
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self.headers = {"X-Device-ID": device_id}

    # ===== 认证 =====

    async def activate(self, invite_code: str, username: str) -> dict:
        """用邀请码激活设备"""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/api/auth/activate",
                json={
                    "invite_code": invite_code,
                    "username": username,
                    "device_id": self.device_id,
                },
            )
            if resp.status_code != 200:
                detail = resp.json().get("detail", "未知错误")
                raise Exception(detail)
            return resp.json()

    async def get_user(self) -> dict | None:
        """获取用户信息（检查是否已激活）"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.base_url}/api/auth/me",
                    headers=self.headers,
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except (httpx.ConnectError, httpx.TimeoutException):
            return None

    # ===== 对话 =====

    async def list_conversations(self) -> list[dict]:
        """获取对话列表"""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/api/conversations",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def create_conversation(self, title: str | None = None) -> dict:
        """创建新对话"""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/api/conversations",
                json={"title": title} if title else {},
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_conversation(self, conv_id: str):
        """删除对话"""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                f"{self.base_url}/api/conversations/{conv_id}",
                headers=self.headers,
            )
            resp.raise_for_status()

    async def get_messages(self, conv_id: str) -> list[dict]:
        """获取对话消息"""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/api/conversations/{conv_id}/messages",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    # ===== AI 聊天 =====

    async def chat_stream(
        self, conv_id: str, content: str
    ) -> AsyncGenerator[dict, None]:
        """流式 AI 对话 — 生成 SSE 事件

        Yields:
            SSE 事件字典：{"type": "start"|"chunk"|"result"|"error"|"done", ...}
        """
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={"conversation_id": conv_id, "content": content},
                headers=self.headers,
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    try:
                        detail = json.loads(body).get("detail", "请求失败")
                    except json.JSONDecodeError:
                        detail = f"HTTP {resp.status_code}"
                    raise Exception(detail)

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue
