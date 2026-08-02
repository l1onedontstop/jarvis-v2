#!/usr/bin/env python3
"""
贾维斯 v2 — 语音助手唯一入口。

启动即运行完整语音管道（唤醒、声纹、ASR、TTS、引擎桥接、API 服务器）。
所有参数直接透传给 voice_assistant.main()（如 --provider）。
"""

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_DIR / "src"))
sys.path.insert(0, str(_PROJECT_DIR / "src" / "speech"))

from speech.voice_assistant import main as voice_main


if __name__ == "__main__":
    voice_main()
