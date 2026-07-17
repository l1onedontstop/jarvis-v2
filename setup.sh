#!/bin/bash
# 贾维斯 v2 — 一键安装脚本
# 用途：检查环境、安装依赖、生成配置、验证模型
# 用法：./setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 颜色 ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PASS="${GREEN}✓${NC}"
FAIL="${RED}✗${NC}"
WARN="${YELLOW}⚠${NC}"

STATUS_PASS=()
STATUS_WARN=()
STATUS_FAIL=()

ok()   { STATUS_PASS+=("$1"); echo -e "  ${PASS} $1"; }
warn() { STATUS_WARN+=("$1"); echo -e "  ${WARN} $1 — $2"; }
fail() { STATUS_FAIL+=("$1"); echo -e "  ${FAIL} $1 — $2"; }

echo ""
echo -e "${BOLD}${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   贾维斯 v2 — 安装向导                ║${NC}"
echo -e "${BOLD}${CYAN}╚════════════════════════════════════════╝${NC}"
echo ""

# ── 系统检查 ──────────────────────────────────────────
echo -e "${BOLD}🔍 系统环境检查${NC}"
echo "──────────────────────────────────────────"

# macOS
if [[ "$(uname)" == "Darwin" ]]; then
    VER=$(sw_vers -productVersion 2>/dev/null || echo "unknown")
    ok "macOS ${VER}"
else
    fail "macOS" "仅支持 macOS。当前系统: $(uname)"
fi

# 芯片架构
ARCH=$(uname -m)
case "$ARCH" in
    arm64) ok "芯片架构: Apple Silicon (arm64)" ;;
    x86_64) warn "芯片架构: Intel (x86_64)" "Apple Silicon 体验更佳" ;;
    *) fail "芯片架构" "未知架构: $ARCH" ;;
esac

# Python
PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        PYVER=$("$candidate" --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo "$PYVER" | cut -d. -f1)
        MINOR=$(echo "$PYVER" | cut -d. -f2)
        if [[ "$MAJOR" -ge 3 && "$MINOR" -ge 10 ]]; then
            PYTHON="$candidate"
            ok "Python ${PYVER} ($candidate)"
            break
        fi
    fi
done
if [[ -z "$PYTHON" ]]; then
    fail "Python 3.10+" "未找到。请安装: brew install python@3.12"
fi

# pip
if command -v pip3 &>/dev/null; then
    ok "pip3 可用"
elif [[ -n "$PYTHON" ]]; then
    warn "pip3" "将用 $PYTHON -m pip 代替"
fi

# Claude Code CLI
if command -v claude &>/dev/null; then
    CLVER=$(claude --version 2>&1 | head -1 || echo "installed")
    ok "Claude Code CLI: ${CLVER}"
elif [ -f /usr/local/bin/claude ]; then
    ok "Claude Code CLI: /usr/local/bin/claude"
else
    warn "Claude Code CLI" "未检测到。请安装: npm i -g @anthropic-ai/claude-code"
fi

# Flutter
FLUTTER_OK=false
if command -v flutter &>/dev/null; then
    FLVER=$(flutter --version 2>&1 | head -1 || echo "installed")
    ok "Flutter: ${FLVER}"
    FLUTTER_OK=true
else
    warn "Flutter" "未找到。HUD 悬浮窗将不可用。安装: brew install flutter"
fi

# CocoaPods (Flutter macOS 构建需要)
if command -v pod &>/dev/null; then
    ok "CocoaPods: $(pod --version 2>/dev/null || echo installed)"
elif [ -f /opt/homebrew/bin/pod ] || [ -f /usr/local/bin/pod ]; then
    ok "CocoaPods installed"
else
    warn "CocoaPods" "未找到。Control Center 构建需要。安装: sudo gem install cocoapods"
fi

# Xcode Command Line Tools
if xcode-select -p &>/dev/null; then
    ok "Xcode CLT 已安装"
else
    warn "Xcode CLT" "未安装。运行: xcode-select --install"
fi

# ffmpeg (音频处理)
if command -v ffmpeg &>/dev/null; then
    ok "ffmpeg: $(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f3)"
else
    warn "ffmpeg" "未找到。Piper TTS 金属音效需要。安装: brew install ffmpeg"
fi

# 磁盘空间（模型约需 1.5GB）
AVAIL_GB=$(df -g . | tail -1 | awk '{print $4}')
if [[ "$AVAIL_GB" -lt 3 ]]; then
    warn "磁盘空间" "可用 ${AVAIL_GB}GB，模型需要约 1.5GB"
else
    ok "磁盘空间: ${AVAIL_GB}GB 可用"
fi

echo ""

# ── Python 虚拟环境 ────────────────────────────────────
echo -e "${BOLD}🐍 Python 环境${NC}"
echo "──────────────────────────────────────────"

if [[ -z "$PYTHON" ]]; then
    fail "Python" "无法继续安装 Python 依赖"
else
    if [ ! -d "venv" ]; then
        echo "  创建虚拟环境..."
        "$PYTHON" -m venv venv
        ok "venv 已创建"
    else
        ok "venv 已存在，跳过创建"
    fi

    echo "  安装 Python 依赖..."
    source venv/bin/activate
    if pip install --prefer-binary -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -5; then
        ok "Python 依赖安装完成"
    else
        # 回退到官方源
        echo "  清华源失败，尝试官方源..."
        if pip install --prefer-binary -r requirements.txt 2>&1 | tail -5; then
            ok "Python 依赖安装完成（官方源）"
        else
            fail "pip install" "依赖安装失败，请检查网络或手动安装"
        fi
    fi
    deactivate
fi

echo ""

# ── 配置文件 ───────────────────────────────────────────
echo -e "${BOLD}⚙️  配置文件${NC}"
echo "──────────────────────────────────────────"

# .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "  创建 .env 文件（从 .env.example 复制）..."
        cp .env.example .env
        echo ""
        echo -e "  ${YELLOW}📝 请配置 .env 文件中的关键参数：${NC}"
        echo ""
        echo -e "     ${BOLD}声纹验证阈值${NC}"
        echo "     VOICE_ASSISTANT_SPEAKER_THRESHOLD=0.0"
        echo "     → 设为 0 跳过声纹验证，录入声纹后建议设为 0.4-0.6"
        echo ""
        echo -e "     ${BOLD}活体检测${NC}"
        echo "     VOICE_ASSISTANT_LIVENESS_ENABLED=true"
        echo "     → 如需启用反欺骗检测，设为 true"
        echo ""

        # 交互式配置
        read -rp "  → 是否现在配置声纹阈值？(y/N) " answer
        if [[ "$answer" =~ ^[Yy] ]]; then
            read -rp "    阈值 (0-1，0=跳过，建议0.5): " threshold
            threshold=${threshold:-0.0}
            sed -i '' "s/^VOICE_ASSISTANT_SPEAKER_THRESHOLD=.*/VOICE_ASSISTANT_SPEAKER_THRESHOLD=${threshold}/" .env
            ok "声纹阈值已设为 ${threshold}"
        fi
        ok ".env 已创建"
    else
        warn ".env" ".env.example 不存在，跳过"
    fi
else
    ok ".env 已存在，跳过创建"
fi

# 关键词文件
echo "  合并唤醒关键词..."
mkdir -p config/keywords
cat config/keywords/*.txt > /tmp/jarvis_v2_keywords_global.txt 2>/dev/null || true
ok "关键词已合并"

echo ""

# ── 模型检查 ───────────────────────────────────────────
echo -e "${BOLD}🧠 模型检查${NC}"
echo "──────────────────────────────────────────"

MODEL_DIR="$SCRIPT_DIR/models"
MISSING_MODELS=()

check_model_file() { local desc="$1" path="$2"; if [ -f "$path" ] || [ -d "$path" ]; then ok "$desc"; else MISSING_MODELS+=("$desc — $path"); warn "$desc" "缺失，需手动下载（见 SETUP.md）"; fi; }

check_model_file "KWS 唤醒词"              "$MODEL_DIR/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20/encoder-epoch-13-avg-2-chunk-16-left-64.onnx"
check_model_file "ASR SenseVoice (离线)"    "$MODEL_DIR/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/model.int8.onnx"
check_model_file "ASR Zipformer (流式)"     "$MODEL_DIR/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20/encoder-epoch-99-avg-1.onnx"
check_model_file "VAD 静音检测"              "$MODEL_DIR/silero_vad.onnx"
check_model_file "声纹 3D-Speaker"          "$MODEL_DIR/3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx"
check_model_file "声纹 speaker.onnx"        "$MODEL_DIR/speaker.onnx"
check_model_file "反欺骗 AASIST"            "$MODEL_DIR/aasist-l.onnx"
check_model_file "Piper TTS (贾维斯)"       "$MODEL_DIR/jarvis/en/en_GB/jarvis/high/jarvis-high.onnx"
check_model_file "VITS TTS (林妹妹)"        "$MODEL_DIR/vits-melo-tts-zh_en/model.onnx"

if [[ ${#MISSING_MODELS[@]} -gt 0 ]]; then
    echo ""
    echo -e "  ${YELLOW}缺失 ${#MISSING_MODELS[@]} 个模型，详见 SETUP.md 下载指引${NC}"
fi

echo ""

# ── 目录结构 ───────────────────────────────────────────
echo -e "${BOLD}📁 目录初始化${NC}"
echo "──────────────────────────────────────────"

mkdir -p data/enrollment
mkdir -p logs
mkdir -p keywords
ok "运行时目录已就绪"

echo ""

# ── 权限检查 ───────────────────────────────────────────
echo -e "${BOLD}🔐 系统权限${NC}"
echo "──────────────────────────────────────────"

# 麦克风权限（通过检查 TCC 数据库）
if [[ -d "/Library/Application Support/com.apple.TCC" ]] || sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db "SELECT service FROM access WHERE client='com.apple.Terminal' AND service='kTCCServiceMicrophone'" 2>/dev/null | grep -q .; then
    ok "麦克风权限已授权"
else
    warn "麦克风权限" "请确认 系统设置 > 隐私 > 麦克风 中已允许终端"
fi

# 辅助功能权限
if sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db "SELECT client FROM access WHERE service='kTCCServiceAccessibility'" 2>/dev/null | grep -q .; then
    ok "辅助功能权限已授权"
else
    warn "辅助功能权限" "请确认 系统设置 > 隐私 > 辅助功能 中已允许终端"
fi

echo ""

# ── Flutter UI 构建 ────────────────────────────────────
echo -e "${BOLD}🎨 Flutter UI${NC}"
echo "──────────────────────────────────────────"

if $FLUTTER_OK; then
    # Overlay
    if [ -d "ui/overlay" ]; then
        echo "  构建 HUD Overlay..."
        cd ui/overlay
        if flutter pub get &>/dev/null && flutter build macos --debug &>/dev/null; then
            ok "HUD Overlay 构建成功"
        else
            warn "HUD Overlay" "构建失败，首次运行 start_voice.sh 时会自动尝试"
        fi
        cd "$SCRIPT_DIR"
    else
        warn "HUD Overlay" "ui/overlay 目录不存在，跳过"
    fi

    # Control Center
    if [ -d "ui/control_center" ]; then
        echo "  构建 Control Center..."
        cd ui/control_center
        if flutter pub get &>/dev/null && flutter build macos --debug &>/dev/null; then
            ok "Control Center 构建成功"
            # 注册到 Applications
            CC_APP="build/macos/Build/Products/Debug/control_center.app"
            if [ -d "$CC_APP" ]; then
                if [ ! -d "/Applications/control_center.app" ]; then
                    cp -R "$CC_APP" /Applications/control_center.app 2>/dev/null && \
                        ok "Control Center 已安装到 /Applications" || \
                        warn "Control Center" "复制到 /Applications 失败"
                else
                    ok "Control Center 已存在于 /Applications"
                fi
            fi
        else
            warn "Control Center" "构建失败，首次运行 start_voice.sh 时会自动尝试"
        fi
        cd "$SCRIPT_DIR"
    else
        warn "Control Center" "ui/control_center 目录不存在，跳过"
    fi
else
    warn "Flutter UI" "Flutter 未安装，跳过 UI 构建。HUD + Control Center 不可用"
fi

echo ""

# ── 最终报告 ───────────────────────────────────────────
echo -e "${BOLD}${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   安装报告                            ║${NC}"
echo -e "${BOLD}${CYAN}╚════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}通过 (${#STATUS_PASS[@]})${NC}"
echo -e "${YELLOW}警告 (${#STATUS_WARN[@]})${NC}"
echo -e "${RED}失败 (${#STATUS_FAIL[@]})${NC}"
echo ""

if [[ ${#STATUS_FAIL[@]} -gt 0 ]]; then
    echo -e "${RED}❌ 发现 ${#STATUS_FAIL[@]} 项致命问题，无法继续。请修复后重新运行。${NC}"
fi

echo -e "${BOLD}📋 下一步：${NC}"
echo "  1. 配置 .env 参数（如需）"
echo "  2. 下载缺失模型 → 参考 SETUP.md"
echo "  3. 录入声纹 → source venv/bin/activate && python3 scripts/enroll_speaker.py"
echo "  4. 启动语音模式 → ./start_voice.sh"
echo "  5. 说 「Jarvis」或「贾维斯」唤醒"
echo ""

if [[ ${#STATUS_FAIL[@]} -eq 0 && ${#STATUS_WARN[@]} -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}✅ 安装完成！贾维斯已就绪。${NC}"
elif [[ ${#STATUS_FAIL[@]} -eq 0 ]]; then
    echo -e "${YELLOW}${BOLD}⚠️  安装基本完成，有 ${#STATUS_WARN[@]} 项警告，建议处理后再启动。${NC}"
else
    echo -e "${RED}${BOLD}❌ 安装未完成，请先修复上述问题。${NC}"
fi

echo ""
