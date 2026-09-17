"""命令安全检查器

在本地执行 AI 生成的 shell 命令前进行安全审查：
- 检测危险命令模式（rm -rf, dd, mkfs 等）
- 检测敏感目录访问（/, /etc, /sys 等）
- 检测命令注入风险（反引号、$()、管道到 root shell 等）
- 结合 AI 的 danger_level 做二次确认
"""

import re
import shlex
from enum import Enum
from typing import NamedTuple


class Action(Enum):
    """安全检查后的建议操作"""
    ALLOW = "allow"
    CONFIRM = "confirm"      # 需要用户确认
    BLOCK = "block"          # 直接阻止


class SafetyResult(NamedTuple):
    """安全检查结果"""
    action: Action
    reason: str              # 中文说明
    risks: list[str]         # 发现的具体风险项


# ===== 危险命令模式 =====

# 禁止执行的模式 — 直接 BLOCK
BLOCKED_PATTERNS = [
    (r"\brm\s+-rf\s+/\s*$", "递归删除根目录，将摧毁整个文件系统"),
    (r"\brm\s+-rf\s+/\s+", "递归删除根目录附近内容，极度危险"),
    (r"\bmkfs\b", "格式化文件系统，数据全部丢失"),
    (r"\bdd\b.*\bof=/dev/", "直接写入块设备，可能覆盖整个磁盘"),
    (r">\s*/dev/sd[a-z]", "直接写入磁盘设备"),
    (r":\(\)\s*\{.*\}.*;", "fork bomb，将耗尽系统资源"),
    (r"\bshutdown\b", "关机命令"),
    (r"\breboot\b", "重启命令"),
    (r"\bhalt\b", "停机命令"),
    (r"\bpoweroff\b", "关机命令"),
    (r"\biptables\s+-F", "清空防火墙规则，可能导致网络失联"),
    (r"\bip\s+route\s+del\s+default", "删除默认路由，将断网"),
    (r"\bkill\s+-9\s+1\b", "杀死 init 进程"),
    (r"\bkillall\s+-9", "强制杀死所有同名进程"),
    (r"\bkill\s+-9\s+-1\b", "杀死所有用户进程"),
]

# 需要确认的模式 — CONFIRM
CONFIRM_PATTERNS = [
    (r"\brm\s+(-[rfRF]+|--force)\b", "删除操作，文件不可恢复"),
    (r"\bmv\b.*\s+/dev/null", "将文件移入 /dev/null，等同于删除"),
    (r"\bchmod\s+(-R\s+)?0?777\b", "递归设置 777 权限，安全风险"),
    (r"\bchown\s+-R\b", "递归修改所有者，影响范围大"),
    (r"\bkill\s+-9\b", "强制杀死进程（SIGKILL）"),
    (r"\bkill\s+-KILL\b", "强制杀死进程"),
    (r"\bpkill\b", "按名称杀死进程"),
    (r"\bkillall\b", "杀死所有同名进程"),
    (r"\bdocker\s+rm\s+-f", "强制删除容器"),
    (r"\bdocker\s+rmi\s+-f", "强制删除镜像"),
    (r"\bgit\s+push\s+--force", "强制推送，覆盖远程历史"),
    (r"\bgit\s+reset\s+--hard", "硬重置，本地修改全部丢失"),
    (r"\bgit\s+clean\s+-fd", "删除未跟踪文件和目录"),
    (r"\bcurl\b.*\|\s*sh", "管道执行远程脚本，风险极高"),
    (r"\bwget\b.*\|\s*sh", "管道执行远程脚本，风险极高"),
    (r"\bcurl\b.*\|\s*bash", "管道执行远程脚本，风险极高"),
    (r"\bwget\b.*\|\s*bash", "管道执行远程脚本，风险极高"),
    (r"\bmkswap\b", "创建交换区，将覆盖目标设备数据"),
    (r"\bmount\b.*\b-o\b.*remount", "重新挂载文件系统"),
]

# 敏感目录 — 任何写操作都需要确认
SENSITIVE_PATHS = [
    "/etc",
    "/sys",
    "/proc",
    "/boot",
    "/dev",
    "/var/log",
    "/usr/bin",
    "/usr/sbin",
    "/usr/lib",
    "/root",
]

# 命令注入检测模式
INJECTION_PATTERNS = [
    (r"[^`]`[^`]+`", "反引号命令替换，可能执行意外命令"),
    (r"\$\([^)]+\)", "$() 命令替换，可能执行意外命令"),
    (r"\beval\b", "eval 执行任意代码"),
    (r"\bexec\b", "exec 替换当前进程"),
    (r"\bsource\b.*\|\s*sh", "source 后管道执行"),
    (r"\bexport\b.*=\$\(.*\)", "环境变量赋值中嵌入命令执行"),
]


def check_command(command: str, ai_danger_level: str = "safe") -> SafetyResult:
    """对命令进行安全检查

    Args:
        command: AI 生成的 shell 命令
        ai_danger_level: AI 判定的危险等级 (safe/warn/danger)

    Returns:
        SafetyResult: 建议操作 + 原因 + 风险列表
    """
    risks = []
    cmd = command.strip()

    if not cmd:
        return SafetyResult(Action.ALLOW, "空命令", [])

    # 1. 检查禁止模式
    for pattern, desc in BLOCKED_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            risks.append(f"[BLOCKED] {desc}")
            return SafetyResult(
                Action.BLOCK,
                f"检测到禁止执行的命令：{desc}",
                risks,
            )

    # 2. 检查注入风险
    for pattern, desc in INJECTION_PATTERNS:
        if re.search(pattern, cmd):
            risks.append(f"[INJECTION] {desc}")

    # 3. 检查需要确认的模式
    for pattern, desc in CONFIRM_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            risks.append(f"[CONFIRM] {desc}")

    # 4. 检查敏感目录写操作
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()

    for path in SENSITIVE_PATHS:
        # 检查命令参数中是否包含敏感路径
        path_in_cmd = any(
            token == path or token.startswith(path + "/")
            for token in tokens
        )
        if path_in_cmd and _is_write_command(tokens[0] if tokens else ""):
            risks.append(f"[SENSITIVE] 访问敏感路径 {path}")

    # 5. 根据 AI danger_level 和检测结果决定操作
    if ai_danger_level == "danger":
        if not risks:
            risks.append("[AI] AI 判定为 danger 级别")
        return SafetyResult(
            Action.CONFIRM,
            "AI 判定此命令为危险操作，需要二次确认",
            risks,
        )

    if risks:
        # 有风险但未 BLOCK 的，需要确认
        has_injection = any("[INJECTION]" in r or "[BLOCKED]" in r for r in risks)
        if has_injection and ai_danger_level != "danger":
            return SafetyResult(
                Action.CONFIRM,
                "检测到潜在命令注入风险，请仔细检查命令内容",
                risks,
            )
        return SafetyResult(
            Action.CONFIRM,
            f"检测到 {len(risks)} 个风险项，需要确认",
            risks,
        )

    if ai_danger_level == "warn":
        return SafetyResult(
            Action.CONFIRM,
            "AI 判定此命令为警告级别，建议确认后执行",
            ["[AI] AI 判定为 warn 级别"],
        )

    return SafetyResult(Action.ALLOW, "命令安全，可以执行", [])


def _is_write_command(cmd_name: str) -> bool:
    """判断命令是否为写操作"""
    write_cmds = {
        "rm", "mv", "cp", "mkdir", "rmdir", "touch", "chmod", "chown",
        "dd", "tee", "truncate", "ln", "install", "rsync",
        ">",
    }
    return cmd_name in write_cmds or cmd_name == ">"


def format_risks(risks: list[str]) -> str:
    """格式化风险列表为显示文本"""
    if not risks:
        return ""
    lines = ["发现以下风险:"]
    for r in risks:
        # [TAG] description → ● description
        tag_end = r.find("]")
        if tag_end != -1:
            desc = r[tag_end + 2:]
        else:
            desc = r
        lines.append(f"  • {desc}")
    return "\n".join(lines)
