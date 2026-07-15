#!/bin/bash
# 本地视觉分析 — 调用 Ollama MiniCPM-V 分析图像
# 用法: bash scripts/vision_analyze.sh /tmp/test_cam.jpg "描述画面"
set -e
IMAGE="$1"
PROMPT="${2:-请用一句话描述这张照片的内容，使用中文}"

if [ ! -f "$IMAGE" ]; then
    echo '{"error": "image not found"}' >&2
    exit 1
fi

# base64 编码图像
B64=$(base64 -i "$IMAGE" | tr -d '\n')

# 用 python3 构造安全的 JSON 请求
PAYLOAD=$(python3 -c "
import json, sys
payload = {
    'model': 'minicpm-v4.6:1b',
    'prompt': sys.argv[1],
    'images': [sys.argv[2]],
    'stream': False
}
print(json.dumps(payload))
" "$PROMPT" "$B64")

# 调用 Ollama API
RESULT=$(curl -sS http://localhost:11434/api/generate -d "$PAYLOAD" 2>/dev/null)
echo "$RESULT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('response', '分析失败'))
except:
    print('分析失败')
"

# 分析完成后自动卸载模型，释放 CPU/内存
ollama stop minicpm-v4.6:1b &>/dev/null &
