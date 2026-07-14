#!/bin/bash
# 贾维斯 v2 — 语音模式启动（朋友音频管道 + Claude 引擎）
set -e
cd "$(dirname "$0")"
source ./venv/bin/activate

# 合并关键词
echo "🔑 合并关键词..."
mkdir -p keywords
cat config/keywords/*.txt > keywords/global.txt 2>/dev/null || true

# 启动语音助手
echo "⚡ 启动贾维斯 v2（语音模式）..."
python3 -m src.speech.voice_assistant "$@"
