"""AI 服务 — 智谱 GLM-4-Flash 集成

负责调用 LLM API 生成 shell 命令，支持流式和非流式两种模式。
认证方式：Bearer token（API Key 直接使用）。
"""

import json
import re
from typing import AsyncGenerator

import httpx

from app.config import settings


# ===== System Prompt（Prompt 工程）=====

SYSTEM_PROMPT = """你是 ask-tui，一个专业的命令行助手。用户用自然语言描述需求，你生成对应的 shell 命令。

请严格按以下 JSON 格式回复（只输出 JSON，不要 markdown 代码块）：
{
  "thinking": "简要理解用户需求（1-2句中文）",
  "command": "可直接执行的 shell 命令",
  "explanation": "命令各参数的详细解释（中文）",
  "danger_level": "safe 或 warn 或 danger"
}

危险等级判定标准：
- safe: 只读操作，不修改系统（ls, cat, grep, find, df, du, ps, top, head, tail）
- warn: 可恢复的修改操作（mv, cp, mkdir, chmod, touch, tar, zip, unzip）
- danger: 不可逆操作，可能导致数据丢失（rm -rf, dd, mkfs, kill -9, shutdown, reboot）

规则：
1. 只输出 JSON，不要任何其他文字或 markdown 格式
2. command 字段必须是可直接在终端执行的完整命令
3. 如果用户需求不明确，在 thinking 中说明，并给出最可能的命令
4. 优先使用跨平台兼容的命令（兼容 Linux 和 macOS）
5. 对于 danger 级别命令，在 explanation 中强调风险提示
6. 不要用 sudo 前缀，由用户自行决定是否提权
"""


def parse_ai_response(content: str) -> dict:
    """解析 AI 返回的 JSON 响应

    GLM-4-Flash 通常能严格输出 JSON，但也做容错处理：
    - 移除可能的 markdown 代码块包裹
    - JSON 解析失败时降级为纯文本解释

    Returns:
        {"thinking", "command", "explanation", "danger_level"}
    """
    cleaned = content.strip()

    # 移除可能的 markdown 代码块
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

    try:
        data = json.loads(cleaned)
        return {
            "thinking": data.get("thinking", ""),
            "command": data.get("command", ""),
            "explanation": data.get("explanation", ""),
            "danger_level": data.get("danger_level", "safe"),
        }
    except (json.JSONDecodeError, TypeError):
        return {
            "thinking": "",
            "command": "",
            "explanation": content,
            "danger_level": "safe",
        }


async def chat_completion_stream(messages: list[dict]) -> AsyncGenerator[str, None]:
    """流式调用 GLM-4-Flash

    Args:
        messages: 消息列表 [{"role": "system"|"user"|"assistant", "content": "..."}]

    Yields:
        AI 响应的文本块（增量）
    """
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 1000,
    }
    url = f"{settings.LLM_BASE_URL}/chat/completions"

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST", url, json=payload, headers=headers
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise RuntimeError(
                    f"LLM API 错误 {resp.status_code}: {body.decode()}"
                )

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


async def chat_completion(messages: list[dict]) -> str:
    """非流式调用 GLM-4-Flash

    Returns:
        AI 完整响应文本
    """
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 1000,
    }
    url = f"{settings.LLM_BASE_URL}/chat/completions"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
