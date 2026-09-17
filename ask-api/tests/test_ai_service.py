"""AI 服务单元测试

测试 parse_ai_response 解析逻辑（纯函数，无需 mock）。
"""

import pytest
from app.services.ai_service import parse_ai_response, SYSTEM_PROMPT


class TestParseAIResponse:
    """解析 AI 响应测试"""

    @pytest.mark.asyncio
    async def test_valid_json(self):
        """标准 JSON 响应"""
        content = '{"thinking": "查找大文件", "command": "find . -size +1G", "explanation": "使用 find 命令", "danger_level": "safe"}'
        result = parse_ai_response(content)
        assert result["thinking"] == "查找大文件"
        assert result["command"] == "find . -size +1G"
        assert result["explanation"] == "使用 find 命令"
        assert result["danger_level"] == "safe"

    @pytest.mark.asyncio
    async def test_json_with_code_block(self):
        """被 markdown 代码块包裹的 JSON"""
        content = '```json\n{"thinking": "测试", "command": "ls -la", "explanation": "列文件", "danger_level": "safe"}\n```'
        result = parse_ai_response(content)
        assert result["command"] == "ls -la"
        assert result["danger_level"] == "safe"

    @pytest.mark.asyncio
    async def test_json_plain_code_block(self):
        """被无标记代码块包裹的 JSON"""
        content = '```\n{"thinking": "测试", "command": "pwd", "explanation": "显示路径", "danger_level": "safe"}\n```'
        result = parse_ai_response(content)
        assert result["command"] == "pwd"

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self):
        """非 JSON 降级为纯文本"""
        content = "这不是一个有效的 JSON 响应"
        result = parse_ai_response(content)
        assert result["command"] == ""
        assert result["explanation"] == content
        assert result["danger_level"] == "safe"

    @pytest.mark.asyncio
    async def test_missing_fields(self):
        """JSON 缺少部分字段"""
        content = '{"command": "ls"}'
        result = parse_ai_response(content)
        assert result["command"] == "ls"
        assert result["thinking"] == ""
        assert result["explanation"] == ""
        assert result["danger_level"] == "safe"

    @pytest.mark.asyncio
    async def test_danger_level(self):
        """危险等级传递"""
        content = '{"thinking": "删除", "command": "rm -rf /", "explanation": "危险", "danger_level": "danger"}'
        result = parse_ai_response(content)
        assert result["danger_level"] == "danger"

    @pytest.mark.asyncio
    async def test_warn_level(self):
        """警告等级"""
        content = '{"thinking": "移动", "command": "mv a b", "explanation": "移动文件", "danger_level": "warn"}'
        result = parse_ai_response(content)
        assert result["danger_level"] == "warn"

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """空内容"""
        result = parse_ai_response("")
        assert result["command"] == ""
        assert result["danger_level"] == "safe"

    @pytest.mark.asyncio
    async def test_extra_whitespace(self):
        """JSON 前后有多余空格"""
        content = '  \n {"thinking": "测试", "command": "echo hi", "explanation": "打印", "danger_level": "safe"} \n  '
        result = parse_ai_response(content)
        assert result["command"] == "echo hi"

    @pytest.mark.asyncio
    async def test_system_prompt_content(self):
        """系统提示词包含关键要素"""
        assert "JSON" in SYSTEM_PROMPT
        assert "command" in SYSTEM_PROMPT
        assert "danger_level" in SYSTEM_PROMPT
        assert "safe" in SYSTEM_PROMPT
        assert "warn" in SYSTEM_PROMPT
        assert "danger" in SYSTEM_PROMPT
        assert "shell" in SYSTEM_PROMPT
