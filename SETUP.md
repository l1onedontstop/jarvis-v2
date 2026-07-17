# 贾维斯 v2 — 安装指引

> 推荐先运行 `./setup.sh` 自动完成大部分步骤，然后按本文档补全手动步骤。

---

## 目录

1. [前置依赖](#1-前置依赖)
2. [模型下载](#2-模型下载)
3. [配置文件](#3-配置文件)
4. [Flutter UI 构建](#4-flutter-ui-构建)
5. [系统权限](#5-系统权限)
6. [声纹录入](#6-声纹录入)
7. [首次启动验证](#7-首次启动验证)
8. [常见问题](#8-常见问题)

---

## 1. 前置依赖

| 依赖 | 用途 | 安装方式 |
|------|------|---------|
| macOS 14+ | 运行环境 | — |
| Python 3.10+ | 核心运行时 | `brew install python@3.12` |
| Claude Code CLI | AI 对话引擎 | `npm i -g @anthropic-ai/claude-code`，然后 `claude login` |
| Flutter 3.24+ | HUD 悬浮窗 | `brew install flutter` |
| CocoaPods | Control Center 构建 | `sudo gem install cocoapods` |
| Xcode CLT | macOS 原生编译 | `xcode-select --install` |
| ffmpeg | TTS 音频后处理 | `brew install ffmpeg` |

### 验证安装

```bash
python3 --version    # ≥ 3.10
claude --version     # 应显示版本号
flutter --version    # ≥ 3.24
pod --version        # CocoaPods
ffmpeg -version      # 用于音频后处理
```

---

## 2. 模型下载

模型总计约 **1.5GB**，存放在 `models/` 目录下。

### 2.1 语音识别模型 (sherpa-onnx)

所有 sherpa-onnx 模型从 GitHub Releases 下载。

```bash
MODEL_DIR="$(pwd)/models"
mkdir -p "$MODEL_DIR"

# KWS 唤醒词检测 (~40MB)
curl -L "https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20.tar.bz2" \
  | tar xj -C "$MODEL_DIR"

# ASR SenseVoice 离线识别 (~180MB，int8 量化)
curl -L "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2" \
  | tar xj -C "$MODEL_DIR"

# ASR Zipformer 流式识别 (~75MB)
curl -L "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2" \
  | tar xj -C "$MODEL_DIR"

# VAD 静音检测 (~2MB)
curl -L "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx" \
  -o "$MODEL_DIR/silero_vad.onnx"

# 注：国内用户可将 github.com 替换为 hub.nuaa.cf 或使用代理
```

### 2.2 声纹模型

```bash
# 3D-Speaker 声纹提取 (~28MB)
curl -L "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx" \
  -o "$MODEL_DIR/3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx"

# 声纹嵌入模型 (~28MB)
curl -L "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx" \
  -o "$MODEL_DIR/speaker.onnx"

# 反欺骗 AASIST-L (~0.7MB)
curl -L "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/aasist-l.onnx" \
  -o "$MODEL_DIR/aasist-l.onnx"
```

### 2.3 TTS 语音合成模型

**贾维斯英音 (Piper TTS)**

从 HuggingFace Piper Voices 下载 `en_GB-jarvis-high`：

```bash
mkdir -p "$MODEL_DIR/jarvis/en/en_GB/jarvis/high"

# 模型 + 配置
curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/jarvis/high/en_GB-jarvis-high.onnx" \
  -o "$MODEL_DIR/jarvis/en/en_GB/jarvis/high/jarvis-high.onnx"

curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/jarvis/high/en_GB-jarvis-high.onnx.json" \
  -o "$MODEL_DIR/jarvis/en/en_GB/jarvis/high/jarvis-high.onnx.json"

curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/jarvis/high/tokens.txt" \
  -o "$MODEL_DIR/jarvis/en/en_GB/jarvis/high/tokens.txt"
```

> 💡 也可安装 medium 质量版（文件更小）。将以上 `high` 替换为 `medium`。代码默认用 high。

**林妹妹中文 (VITS MeloTTS)**

```bash
# 从 HuggingFace 下载 MeloTTS 中文模型
mkdir -p "$MODEL_DIR/vits-melo-tts-zh_en"

curl -L "https://huggingface.co/myshell-ai/MeloTTS-English/resolve/main/baker/models/baker.onnx" \
  -o "$MODEL_DIR/vits-melo-tts-zh_en/model.onnx"  # 中文 baker 模型
```

> MeloTTS 中文源模型在 [MeloTTS-Chinese](https://huggingface.co/myshell-ai/MeloTTS-Chinese/tree/main/baker/models)。如链接失效，请用对应 HuggingFace 页面查询最新路径。

### 2.4 验证模型完整性

```bash
python3 scripts/model_cli.py check   # 如果脚本支持
# 或手动检查文件：
ls -lh models/*.onnx
ls models/sherpa-onnx-*/   # 应有多个子目录
ls models/jarvis/en/en_GB/jarvis/high/
```

---

## 3. 配置文件

### 3.1 环境变量

```bash
cp .env.example .env
```

关键配置项（按需修改）：

```ini
# 声纹验证阈值 (0-1)。0=跳过，建议录入声纹后设为 0.5
VOICE_ASSISTANT_SPEAKER_THRESHOLD=0.0

# 活体检测（需要摄像头）
VOICE_ASSISTANT_LIVENESS_ENABLED=false

# 空闲超时（秒）
VOICE_ASSISTANT_IDLE_TIMEOUT_SECONDS=15

# 媒体播放时唤醒保护
VOICE_ASSISTANT_MEDIA_WAKE_GUARD_ENABLED=true
```

### 3.2 角色配置

`config/assistants.json` 定义角色（贾维斯、林妹妹）。每个角色可独立配置：
- `tts` — TTS 引擎（jarvis / macos_say / custom）
- `keywords_file` — 唤醒关键词列表
- `enabled` — 是否启用

---

## 4. Flutter UI 构建

### 4.1 HUD Overlay

粒子特效悬浮窗，语音交互时显示：

```bash
cd ui/overlay
flutter pub get
flutter build macos --debug
cd ../..
```

### 4.2 Control Center

调试面板，显示日志、状态、配置：

```bash
cd ui/control_center
flutter pub get
flutter build macos --debug
# 注册到 Applications
cp -R build/macos/Build/Products/Debug/control_center.app /Applications/
cd ../..
```

> 构建后在 `start_voice.sh` 中会自动打开已安装的 `.app`。

---

## 5. 系统权限

贾维斯需要以下 macOS 权限才能正常工作：

| 权限 | 用途 | 设置路径 |
|------|------|---------|
| 🎙️ **麦克风** | 语音输入 | 系统设置 → 隐私与安全性 → 麦克风 |
| ♿ **辅助功能** | 系统控制、微信发送 | 系统设置 → 隐私与安全性 → 辅助功能 |
| 🖥️ **屏幕录制** | 截屏分析（可选） | 系统设置 → 隐私与安全性 → 屏幕录制 |

### 检查当前权限

```bash
# 麦克风
system_profiler SPAudioDataType | grep -i input

# 辅助功能（需要数据库读取权限）
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db \
  "SELECT client, allowed FROM access WHERE service='kTCCServiceAccessibility'" 2>/dev/null
```

> 首次运行时，macOS 会自动弹出权限请求对话框。请点击"允许"。

---

## 6. 声纹录入

为确保只有你的声音能唤醒贾维斯，需要录一声纹样本。

```bash
source venv/bin/activate
python3 scripts/enroll_speaker.py
```

录制过程中：
1. 在 20 秒内重复朗读 **「Is JARVIS here」**
2. 每次朗读之间稍作停顿
3. 系统会自动提取声纹并保存到 `data/enrollment/`

### 验证声纹

```bash
python3 scripts/enroll_speaker.py --list
```

### 启用声纹验证

编辑 `.env`，设置阈值：

```ini
VOICE_ASSISTANT_SPEAKER_THRESHOLD=0.5
```

- `0.3-0.4` — 宽松，容易通过
- `0.5-0.6` — 推荐，平衡安全性和便利性
- `0.7+` — 严格，可能频繁拒绝

---

## 7. 首次启动验证

### 7.1 测试麦克风

```bash
source venv/bin/activate
python3 scripts/test_mic.py
```

对麦克风说话，确认能正常录音。

### 7.2 测试语音识别

```bash
source venv/bin/activate
python3 scripts/test_asr.py
```

说几句话，检查识别结果。

### 7.3 启动语音助手

```bash
./start_voice.sh
```

首次启动会：
1. 加载所有模型
2. 初始化声纹验证
3. 启动 Flutter HUD
4. 开始监听唤醒词

说 **"Jarvis"** 或 **"贾维斯"**，出现 HUD 特效并听到 "Reporting for duty, sir" 即表示成功。

### 7.4 快速测试指令

唤醒后直接说：

> "现在几点" — 测试基础对话
> "锁屏" — 测试系统控制
> "退下" — 退出对话

---

## 8. 常见问题

### Q: 唤醒词检测不灵敏？
- `.env` 中调整模型参数（需要修改源码）
- 确保环境安静，麦克风距离适中
- 检查 `config/keywords/jarvis.txt` 包含你的发音方式

### Q: TTS 没有声音？
- 检查 `config/assistants.json` 中 TTS 配置是否正确
- 运行 `ffmpeg -version` 确认 ffmpeg 可用（金属音效需要）
- 检查系统音量和输出设备

### Q: Flutter 构建报错？
- 确认 CocoaPods 已安装：`sudo gem install cocoapods`
- 在 `ui/overlay/ios` 目录运行 `pod install`
- 尝试 `flutter clean && flutter pub get && flutter build macos`

### Q: 国内下载模型很慢？
- sherpa-onnx 模型：将 URL 中 `github.com` 替换为镜像站
- HuggingFace 模型：设置 `export HF_ENDPOINT=https://hf-mirror.com`
- 或从其他渠道下载后手动放入 `models/` 目录

### Q: 微信发送不工作？
- 确认辅助功能权限已授权
- 微信需要在前台运行
- 检查是否有多个微信实例

### Q: Python 依赖安装失败？
- `aec-audio-processing-fork` 可能需要从源码编译
- 使用清华源：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
- 如 `piper-tts` 失败，确认是 `piper-tts` 而非 `piper`
