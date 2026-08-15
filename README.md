# J.A.R.V.I.S. v2 — macOS AI 语音助手

> "At your service, sir."

贾维斯 (J.A.R.V.I.S.) 是一个运行在 macOS 上的 AI 语音助手。支持**语音唤醒**、**声纹验证**、**多 Agent 协作**、**Flutter HUD 悬浮窗**，由 **Claude Code** 驱动对话智能。

---

## ✨ 功能

| 模块 | 说明 |
|------|------|
| 🎙️ **语音唤醒** | 离线唤醒词检测（sherpa-onnx KWS），说 "Jarvis" / "贾维斯" 即唤醒 |
| 🧠 **Claude Code 驱动** | 全功能 AI 助手：问答、文件操作、系统控制、网页搜索 |
| 🗣️ **TTS 语音合成** | JARVIS-V2 MeloTTS ONNX 中英混合语音（默认）+ 可选 Piper 英音 + VITS 中文 |
| 🔐 **声纹验证** | 3D-Speaker 声纹识别，只有你的声音能唤醒 |
| 🤖 **Agent 编排** | 说"组队"自动进入多 Agent 协作模式 |
| 🖥️ **Flutter HUD** | 粒子效果悬浮窗 + 控制中心调试面板 |
| ⚡ **Quick Actions** | 本地快速指令（锁屏、休眠、音量、亮度等 29 条） |
| 📋 **系统集成** | 日历、提醒事项、微信发送（macOS 辅助功能） |
| 🎬 **打断词** | 播报中说 "shut up" / "wait wait" 打断 TTS |
| 🔄 **上下文持久** | 历史对话存 JSONL，重启不丢 |

---

## 🖼️ 架构

```
┌─────────────────────────────────────────────────────┐
│                    语音前端                          │
│  唤醒词检测 → VAD → ASR → 声纹验证 → 活体检测        │
└──────────────────────┬──────────────────────────────┘
                       │ 转录文本
┌──────────────────────▼──────────────────────────────┐
│                    智能层                            │
│  Quick Actions ← 路由 → Claude Code (持久会话)       │
│                        → Agent 编排 (多 Agent)       │
└──────────────────────┬──────────────────────────────┘
                       │ 文本响应
┌──────────────────────▼──────────────────────────────┐
│                    输出层                            │
│  TTS 合成 → Flutter HUD → 系统通知 → 微信发送         │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

> 完整安装指引见 **[SETUP.md](SETUP.md)**

```bash
# 一键安装
git clone <repo-url> jarvis-v2
cd jarvis-v2
./setup.sh

# 录入你的声纹
source venv/bin/activate
python3 scripts/enroll_speaker.py

# 启动语音模式
./start_voice.sh
```

说 **"Jarvis"** 或 **"贾维斯"** 唤醒。

默认贾维斯 TTS 使用 `jarvis_v2_onnx_lang_sch`，模型目录为
`models/jarvis-v2-melotts-onnx-lang-sch/`。模型来源为 ModelScope 数据集
`rubintry/jarvis` 中的 `jarvis-v2-melotts-onnx-lang-sch.zip`；模型文件不会提交到仓库。
旧的英文 Piper 声音仍可通过 `config/assistants.json` 中的 `jarvis` 配置独立选择。

---

## 📋 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | macOS 14+ (Apple Silicon 推荐) |
| Python | 3.10+ |
| Claude Code | `claude` CLI 已安装并登录 |
| Flutter | 3.24+（HUD 悬浮窗 + 控制中心） |
| 麦克风权限 | 已授权 |
| 辅助功能权限 | 已授权（系统控制、微信发送） |

---

## 📁 目录结构

```
jarvis-v2/
├── src/
│   ├── speech/          # 语音管线：唤醒词→VAD→ASR→对话→TTS
│   ├── intelligence/    # AI 层：Claude桥接、QuickActions、路由
│   ├── adapters/        # 系统集成：日历、提醒、微信、系统控制
│   └── main.py          # 入口
├── config/              # 助手配置、关键词、快捷指令定义
├── models/              # MeloTTS ONNX + sherpa-onnx + Piper + VITS 模型
├── ui/                  # Flutter HUD + Control Center
├── scripts/             # 工具脚本（声纹录入、测试等）
├── prompts/             # SOUL.md 角色提示词
├── data/                # 运行时数据（声纹、对话历史）
├── setup.sh             # 一键安装脚本
├── SETUP.md             # 详细安装指引
└── start_voice.sh       # 语音模式启动
```

---

## 🎛️ 快捷指令

唤醒后直接说指令，无需等待：

> "锁屏" / "休眠" / "静音" / "音量 50" / "屏幕亮度最大" / "发微信给XX说YY"

共 29 条本地指令，定义在 `config/quick_actions.json`。

---

## 👥 多角色

| 角色 | 唤醒词 | 风格 |
|------|--------|------|
| 贾维斯 | "Jarvis" / "贾维斯" | 专业英式管家，Tony Stark's workshop |
| 林妹妹 | "林妹妹" | 红楼梦风格，娇俏中文 |

配置在 `config/assistants.json`，可扩展。

---

## 📄 License

MIT
