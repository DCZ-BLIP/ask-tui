"""ask-tui — Textual TUI 应用

三栏布局：对话列表 | 消息记录 | 命令预览
功能：AI 对话 + 命令安全检查 + 本地执行
"""

import asyncio
import subprocess
import shlex

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
)
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from api_client import ApiClient
from config import load_config, save_config
from safety_checker import check_command, format_risks, Action


# ===== 激活界面 =====

class ActivateScreen(ModalScreen):
    """邀请码激活界面"""

    CSS = """
    ActivateScreen {
        align: center middle;
    }
    #activate-form {
        width: 62;
        height: auto;
        padding: 1 2;
        border: solid $primary;
        background: $surface;
    }
    #activate-title {
        text-align: center;
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }
    #activate-error {
        color: $error;
        margin-top: 1;
    }
    """

    def __init__(self, api: ApiClient, config: dict):
        super().__init__()
        self.api = api
        self.config = config

    def compose(self) -> ComposeResult:
        with Vertical(id="activate-form"):
            yield Label("ask-tui 激活", id="activate-title")
            yield Label("邀请码:")
            yield Input(placeholder="ASK-XXXX-XXX", id="invite-code-input")
            yield Label("昵称:")
            yield Input(placeholder="你的昵称", id="username-input")
            yield Button("激活", id="activate-btn", variant="primary")
            yield Static("", id="activate-error")

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id != "activate-btn":
            return

        invite_code = self.query_one("#invite-code-input").value.strip()
        username = self.query_one("#username-input").value.strip()
        error_widget = self.query_one("#activate-error")

        if not invite_code or not username:
            error_widget.update("[red]请填写所有字段[/red]")
            return

        try:
            user = await self.api.activate(invite_code, username)
            self.config["username"] = username
            save_config(self.config)
            self.dismiss(True)
        except Exception as e:
            error_widget.update(f"[red]激活失败: {e}[/red]")


# ===== 命令确认弹窗 =====

class ConfirmScreen(ModalScreen):
    """命令执行确认弹窗

    显示命令内容、风险提示，用户选择执行或取消。
    """

    CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #confirm-box {
        width: 72;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: solid $warning;
        background: $surface;
    }
    #confirm-title {
        text-align: center;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    #confirm-command {
        background: $boost;
        padding: 0 1;
        margin: 1 0;
        border: solid $surface;
        height: auto;
        min-height: 3;
    }
    #confirm-risks {
        color: $warning;
        margin: 1 0;
        height: auto;
    }
    #confirm-buttons {
        layout: horizontal;
        height: 3;
        margin-top: 1;
    }
    #confirm-yes {
        width: 1fr;
        margin-right: 1;
    }
    #confirm-no {
        width: 1fr;
    }
    """

    def __init__(self, command: str, danger_level: str, risks: list[str]):
        super().__init__()
        self.command = command
        self.danger_level = danger_level
        self.risks = risks

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label("⚠ 命令执行确认", id="confirm-title")
            yield Label("即将执行的命令:")
            yield Static(self.command, id="confirm-command")
            if self.risks:
                yield Static(format_risks(self.risks), id="confirm-risks")
            yield Label(f"危险等级: {self.danger_level}")
            with Horizontal(id="confirm-buttons"):
                yield Button("确认执行 (y)", id="confirm-yes", variant="warning")
                yield Button("取消 (n/Esc)", id="confirm-no", variant="default")

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_key(self, event):
        if event.key == "y":
            self.dismiss(True)
        elif event.key == "n" or event.key == "escape":
            self.dismiss(False)


# ===== 命令输出弹窗 =====

class OutputScreen(ModalScreen):
    """命令执行输出弹窗"""

    CSS = """
    OutputScreen {
        align: center middle;
    }
    #output-box {
        width: 80;
        height: auto;
        max-height: 85%;
        padding: 1 2;
        border: solid $accent;
        background: $surface;
    }
    #output-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #output-log {
        height: auto;
        max-height: 40;
        border: solid $surface;
        background: $boost;
        padding: 0 1;
    }
    #output-close {
        margin-top: 1;
        width: 100%;
    }
    """

    def __init__(self, command: str, exit_code: int, output: str, error: str):
        super().__init__()
        self.command = command
        self.exit_code = exit_code
        self.output = output
        self.error = error

    def compose(self) -> ComposeResult:
        with Vertical(id="output-box"):
            color = "green" if self.exit_code == 0 else "red"
            yield Label(
                f"[{color}]命令执行结果 (退出码: {self.exit_code})[/{color}]",
                id="output-title",
            )
            yield RichLog(id="output-log", wrap=True, markup=True)
            yield Button("关闭 (Esc/Enter)", id="output-close", variant="primary")

    def on_mount(self):
        log = self.query_one("#output-log")
        log.write(f"[dim]命令:[/dim] {self.command}")
        log.write("")
        if self.output:
            log.write("[bold]stdout:[/bold]")
            for line in self.output.splitlines():
                log.write(line)
        if self.error:
            log.write("")
            log.write("[bold red]stderr:[/bold red]")
            for line in self.error.splitlines():
                log.write(line)
        if not self.output and not self.error:
            log.write("[dim]（无输出）[/dim]")

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "output-close":
            self.dismiss()

    def on_key(self, event):
        if event.key in ("escape", "enter"):
            self.dismiss()


# ===== 主应用 =====

class AskTuiApp(App):
    """ask-tui — AI 命令行助手"""

    CSS = """
    #main-view {
        layout: horizontal;
        height: 1fr;
    }
    #conversation-panel {
        width: 24;
        border-right: solid $primary;
    }
    #conv-title, #cmd-title {
        text-align: center;
        text-style: bold;
        padding: 0 1;
        background: $boost;
        height: 3;
    }
    #chat-panel {
        width: 1fr;
    }
    #command-panel {
        width: 36;
        border-left: solid $accent;
    }
    #input-bar {
        dock: bottom;
        height: 3;
    }
    #conversation-list {
        height: 1fr;
    }
    #chat-log {
        height: 1fr;
        border: solid $surface;
    }
    #command-display {
        height: 1fr;
        padding: 0 1;
    }
    .conv-item {
        width: 100%;
        text-align: left;
        margin-bottom: 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_conversation", "新对话"),
        Binding("ctrl+d", "delete_conversation", "删除"),
        Binding("ctrl+enter", "execute_command", "执行命令"),
        Binding("ctrl+q", "quit", "退出"),
    ]

    current_conv_id = reactive(None)
    current_command = reactive("")
    current_danger_level = reactive("safe")

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.api = ApiClient(self.config["api_base_url"], self.config["device_id"])
        self.conversations = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-view"):
            with Vertical(id="conversation-panel"):
                yield Label("对话列表", id="conv-title")
                with VerticalScroll(id="conversation-list"):
                    pass
            with Vertical(id="chat-panel"):
                yield RichLog(id="chat-log", wrap=True, markup=True)
            with Vertical(id="command-panel"):
                yield Label("命令预览 (Ctrl+Enter 执行)", id="cmd-title")
                with VerticalScroll(id="command-display-scroll"):
                    yield Static(
                        "[dim]等待命令...[/dim]",
                        id="command-display",
                        markup=True,
                    )
        yield Input(
            placeholder="输入你的需求... (Enter 发送, Ctrl+N 新对话, Ctrl+Enter 执行)",
            id="input-bar",
        )
        yield Footer()

    async def on_mount(self):
        """启动时检查激活状态"""
        chat_log = self.query_one("#chat-log")
        try:
            user = await self.api.get_user()
            if user:
                self.config["username"] = user["username"]
                save_config(self.config)
                await self.refresh_conversations()
            else:
                self.push_screen(
                    ActivateScreen(self.api, self.config),
                    self._on_activated,
                )
        except Exception as e:
            chat_log.write(f"[red]无法连接服务器: {e}[/red]")
            chat_log.write(f"[dim]请检查 config.json 中的 api_base_url[/dim]")

    def _on_activated(self, result: bool):
        """激活成功后的回调"""
        if result:
            self.run_worker(self.refresh_conversations())

    # ===== 对话列表 =====

    async def refresh_conversations(self):
        """刷新对话列表"""
        try:
            self.conversations = await self.api.list_conversations()
        except Exception as e:
            self.query_one("#chat-log").write(f"[red]加载对话列表失败: {e}[/red]")
            return

        list_widget = self.query_one("#conversation-list")
        await list_widget.remove_children()
        for conv in self.conversations:
            title = conv.get("title", "新对话")
            count = conv.get("message_count", 0)
            btn = Button(
                f"{title} ({count})",
                id=f"conv-{conv['id']}",
                classes="conv-item",
            )
            await list_widget.mount(btn)

    async def on_button_pressed(self, event: Button.Pressed):
        """点击对话切换"""
        if event.button.id and event.button.id.startswith("conv-"):
            conv_id = event.button.id[5:]
            self.current_conv_id = conv_id
            await self.load_messages(conv_id)

    async def load_messages(self, conv_id: str):
        """加载对话消息"""
        try:
            messages = await self.api.get_messages(conv_id)
        except Exception as e:
            self.query_one("#chat-log").write(f"[red]加载消息失败: {e}[/red]")
            return

        chat_log = self.query_one("#chat-log")
        chat_log.clear()
        for msg in messages:
            if msg["role"] == "user":
                chat_log.write(f"[bold green]你[/]: {msg['content']}")
            else:
                thinking = msg.get("explanation") or msg.get("content", "")
                chat_log.write(f"[bold blue]AI[/]: {thinking}")
                if msg.get("command"):
                    self.update_command_panel(msg)

    # ===== 聊天输入 =====

    async def on_input_submitted(self, event: Input.Submitted):
        """发送消息"""
        content = event.value.strip()
        if not content:
            return
        if not self.current_conv_id:
            self.query_one("#chat-log").write(
                "[yellow]请先选择或创建对话 (Ctrl+N)[/yellow]"
            )
            return

        event.input.value = ""
        chat_log = self.query_one("#chat-log")
        chat_log.write(f"[bold green]你[/]: {content}")
        self.run_worker(self.do_chat(content), exclusive=True)

    async def do_chat(self, content: str):
        """流式聊天 — 调用 AI 并处理 SSE 事件"""
        chat_log = self.query_one("#chat-log")
        chat_log.write("[dim italic]AI 正在思考...[/dim italic]")
        try:
            async for event in self.api.chat_stream(self.current_conv_id, content):
                etype = event.get("type")
                if etype == "result":
                    self.update_command_panel(event)
                    thinking = event.get("thinking", "")
                    chat_log.write(f"[bold blue]AI[/]: {thinking}")
                elif etype == "error":
                    chat_log.write(f"[red]错误: {event.get('detail', '未知')}[/red]")
        except Exception as e:
            chat_log.write(f"[red]请求失败: {e}[/red]")

    # ===== 命令预览 =====

    def update_command_panel(self, data: dict):
        """更新命令预览面板"""
        cmd_widget = self.query_one("#command-display")
        command = data.get("command", "")
        danger = data.get("danger_level", "safe")
        explanation = data.get("explanation", "")

        # 记录当前命令用于执行
        self.current_command = command
        self.current_danger_level = danger

        danger_colors = {
            "safe": "green",
            "warn": "yellow",
            "danger": "red",
        }
        color = danger_colors.get(danger, "white")
        icon = {"safe": "[green]OK[/]", "warn": "[yellow]!![/]", "danger": "[red]XX[/]"}
        label = icon.get(danger, f"[{color}]{danger.upper()}[/{color}]")

        if command:
            syntax = Syntax(command, "bash", theme="monokai", word_wrap=True)
            lines = [
                syntax,
                "",
                f"{label} [{color}]危险等级: {danger}[/{color}]",
                "",
                f"[dim]Ctrl+Enter 执行此命令[/dim]",
            ]
            if explanation:
                lines.append("")
                lines.append(f"[dim]说明:[/dim]")
                lines.append(explanation)
            panel = Panel(
                "\n".join(str(l) for l in lines),
                title=f"[{color}]命令预览[/{color}]",
                border_style=color,
            )
        else:
            panel = Panel(
                "[dim]无可用命令[/dim]",
                title="命令预览",
                border_style="white",
            )

        cmd_widget.update(panel)

    # ===== 命令执行 =====

    async def action_execute_command(self):
        """Ctrl+Enter: 执行当前预览的命令"""
        command = self.current_command
        if not command:
            self.query_one("#chat-log").write(
                "[yellow]没有可执行的命令，请先发送消息获取 AI 响应[/yellow]"
            )
            return

        # 安全检查
        result = check_command(command, self.current_danger_level)
        chat_log = self.query_one("#chat-log")

        if result.action == Action.BLOCK:
            chat_log.write(f"[red bold]命令被阻止[/red bold]: {result.reason}")
            for risk in result.risks:
                chat_log.write(f"  [red]{risk}[/red]")
            return

        if result.action == Action.CONFIRM:
            # 弹出确认弹窗
            def _on_confirm(confirmed: bool):
                if confirmed:
                    self.run_worker(self._execute(command, chat_log))
                else:
                    chat_log.write(f"[yellow]命令执行已取消[/yellow]")

            self.push_screen(
                ConfirmScreen(command, self.current_danger_level, result.risks),
                _on_confirm,
            )
            return

        # 安全命令直接执行
        self.run_worker(self._execute(command, chat_log))

    async def _execute(self, command: str, chat_log: RichLog):
        """执行 shell 命令并展示输出"""
        chat_log.write(f"[bold cyan]▶ 执行命令:[/bold cyan] {command}")

        try:
            # 使用 subprocess 执行，捕获输出
            # 通过 shell=True 让 shell 解析管道、重定向等
            proc = await asyncio.to_thread(
                subprocess.run,
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,  # 30 秒超时
            )

            exit_code = proc.returncode
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            # 在聊天记录中显示简要结果
            if exit_code == 0:
                chat_log.write(f"[green]✓ 执行成功 (退出码: {exit_code})[/green]")
                if stdout:
                    # 简要显示前几行
                    lines = stdout.strip().splitlines()
                    for line in lines[:5]:
                        chat_log.write(f"  [dim]{line}[/dim]")
                    if len(lines) > 5:
                        chat_log.write(f"  [dim]... (共 {len(lines)} 行，查看完整输出)[/dim]")
            else:
                chat_log.write(f"[red]✗ 执行失败 (退出码: {exit_code})[/red]")
                if stderr:
                    lines = stderr.strip().splitlines()
                    for line in lines[:5]:
                        chat_log.write(f"  [red]{line}[/red]")

            # 弹出完整输出窗口
            self.push_screen(
                OutputScreen(command, exit_code, stdout, stderr)
            )

        except subprocess.TimeoutExpired:
            chat_log.write("[red]✗ 命令执行超时 (30秒)[/red]")
            self.push_screen(
                OutputScreen(command, -1, "", "命令执行超时 (30秒)")
            )
        except Exception as e:
            chat_log.write(f"[red]✗ 执行错误: {e}[/red]")
            self.push_screen(
                OutputScreen(command, -1, "", str(e))
            )

    # ===== 快捷键操作 =====

    async def action_new_conversation(self):
        """Ctrl+N: 新建对话"""
        try:
            conv = await self.api.create_conversation()
            self.current_conv_id = conv["id"]
            await self.refresh_conversations()
            self.query_one("#chat-log").clear()
            self.query_one("#command-display").update("[dim]等待命令...[/dim]")
            self.current_command = ""
        except Exception as e:
            self.query_one("#chat-log").write(f"[red]创建对话失败: {e}[/red]")

    async def action_delete_conversation(self):
        """Ctrl+D: 删除当前对话"""
        if not self.current_conv_id:
            return
        try:
            await self.api.delete_conversation(self.current_conv_id)
            self.current_conv_id = None
            self.current_command = ""
            await self.refresh_conversations()
            self.query_one("#chat-log").clear()
            self.query_one("#command-display").update("[dim]等待命令...[/dim]")
        except Exception as e:
            self.query_one("#chat-log").write(f"[red]删除失败: {e}[/red]")
