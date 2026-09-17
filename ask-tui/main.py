#!/usr/bin/env python3
"""ask-tui — AI 命令行助手 TUI 客户端

启动方式:  python main.py
依赖安装:  pip install -r requirements.txt
配置文件:  ~/.ask-tui/config.json
"""

from app import AskTuiApp


def main():
    app = AskTuiApp()
    app.run()


if __name__ == "__main__":
    main()
