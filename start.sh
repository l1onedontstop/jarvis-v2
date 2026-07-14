#!/bin/bash
# 贾维斯 v2 — 启动脚本
set -e
cd "$(dirname "$0")"

# Python 环境
if [ ! -d "venv" ]; then
    echo "🔧 创建虚拟环境..."
    python3 -m venv venv
    source ./venv/bin/activate
    pip install --prefer-binary -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
else
    source ./venv/bin/activate
fi

# 合并唤醒关键词
echo "🔑 合并关键词..."
mkdir -p config/keywords
cat config/keywords/*.txt > /tmp/jarvis_v2_keywords_global.txt 2>/dev/null || true

# 启动 Flutter HUD
if [ -d "ui/overlay" ]; then
    echo "🎨 启动 HUD Overlay..."
    cd ui/overlay && flutter run -d macos &
    cd ../..
fi

# 启动控制中心
if [ -d "ui/control_center" ]; then
    echo "🎛️ 启动 Control Center..."
    open /Applications/control_center.app 2>/dev/null || true
fi

# 启动语音助手核心
echo "⚡ 启动贾维斯 v2..."
exec python3 -m src.main "$@"
