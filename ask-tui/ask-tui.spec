# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — ask-tui 打包配置

使用方式:
  pyinstaller ask-tui.spec

输出:
  dist/ask-tui (单文件可执行程序)
"""

import sys

block_cipher = None

a = Analysis(
    [
        'main.py',
    ],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Textual 框架内部模块
        'textual.widgets',
        'textual.widgets._input',
        'textual.widgets._button',
        'textual.widgets._static',
        'textual.widgets._label',
        'textual.widgets._footer',
        'textual.widgets._header',
        'textual.widgets._rich_log',
        'textual.containers',
        'textual.screen',
        'textual.binding',
        'textual.reactive',
        'textual.app',
        # Rich 库内部模块
        'rich.syntax',
        'rich.panel',
        'rich.text',
        # 项目自身模块
        'api_client',
        'config',
        'safety_checker',
        'app',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型库
        'tkinter',
        'matplotlib',
        'numpy',
        'PIL',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ask-tui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # 使用单文件模式
    onefile=True,
    # 启动时不在解压目录常驻
    console=True,
    # 使用 --clean 打包时清理临时文件
    clean=True,
)
