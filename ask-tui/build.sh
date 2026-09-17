#!/usr/bin/env bash
# ask-tui 打包构建脚本
#
# 使用方式:
#   chmod +x build.sh
#   ./build.sh
#
# 前置条件:
#   pip install pyinstaller textual httpx rich
#
# 输出:
#   dist/ask-tui (单文件可执行程序)

set -euo pipefail

echo "=========================================="
echo "  ask-tui 打包构建"
echo "=========================================="

# 检查依赖
if ! python -c "import textual" 2>/dev/null; then
    echo "安装依赖..."
    pip install -r requirements.txt
fi

if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "安装 PyInstaller..."
    pip install pyinstaller
fi

# 清理旧构建
echo "清理旧构建..."
rm -rf build/ dist/ *.spec.bak

# 打包
echo "开始打包..."
pyinstaller ask-tui.spec --clean --noconfirm

# 验证
if [ -f "dist/ask-tui" ]; then
    echo ""
    echo "✓ 打包成功!"
    echo "  输出文件: dist/ask-tui"
    echo "  文件大小: $(du -h dist/ask-tui | cut -f1)"
    echo ""
    echo "使用方式:"
    echo "  ./dist/ask-tui"
    echo ""
    echo "分发前修改 config.py 中的默认 API 地址:"
    echo '  "api_base_url": "https://你的域名.com"'
else
    echo "✗ 打包失败!"
    exit 1
fi
