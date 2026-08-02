"""
Speech 包 — 语音管道（KWS + ASR + TTS + 声纹 + 活体检测）。

核心模块：
  voice_assistant    — 完整语音助手（唤醒 → 识别 → 对话 → 播报）
  hermes_bridge      — Hermes 主脑桥接
  openclaw_bridge_websocket — OpenClaw WebSocket 桥接
  tts                — 统一 TTS 入口
  audio              — 音频采集/播放
  anti_spoof         — AASIST 活体检测
  interrupt_keywords — 打断词管理
  routing            — 快路径白名单路由
"""
