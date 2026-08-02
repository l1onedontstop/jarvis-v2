#!/bin/bash
# 贾维斯 v2 — 语音模式启动
set -e
cd "$(dirname "$0")"
source ./venv/bin/activate

# 启动 HUD 特效悬浮窗
if [ -d "/Applications/assistant_overlay.app" ]; then
    echo "🎨 启动 HUD 特效悬浮窗..."
    open /Applications/assistant_overlay.app
fi

# 启动控制中心
if [ -d "/Applications/control_center.app" ]; then
    echo "🎛️ 启动 Control Center..."
    open /Applications/control_center.app
fi

# 合并关键词 + 创建个体映射
echo "🔑 合并关键词..."
mkdir -p keywords
cat config/keywords/*.txt > keywords/global.txt 2>/dev/null || true
for f in config/keywords/*.txt; do
    ln -sf "../$f" "keywords/$(basename $f)" 2>/dev/null || true
done

# 启动语音助手
echo "⚡ 启动贾维斯 v2（语音模式）..."
python3 src/main.py "$@"
