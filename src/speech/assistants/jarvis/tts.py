#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Jarvis TTS — 中英双语合成

英文: Piper (金属感后处理)
中文: ZipVoice 零样本声音克隆（离线，无需网络）
中英混合: ZipVoice 原生支持 zh-en-emilia，连续合成不断流
"""

import os
from threading import Event
import numpy as np

from assistants.tts import AssistantTTS


class JarvisTTS(AssistantTTS):

    def __init__(self, config: dict = None):
        config = config or {}
        from assistants.jarvis import tts_piper, tts_zipvoice
        # Piper 装配金属感 ffmpeg 滤镜链 + speed（英文路径保留）
        tts_piper.configure(config)
        # ZipVoice 装配参考说话人（中文路径，零样本克隆）
        tts_zipvoice.configure(config)

    def is_available(self) -> bool:
        return True

    def _is_chinese(self, text: str) -> bool:
        chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
        return chinese_chars > len(text.replace(' ', '')) * 0.3

    # ── 核心合成接口 ────────────────────────────────────

    def synthesize(self, text: str, output_path: str = None, **kwargs) -> str | None:
        if self._is_chinese(text):
            # 中文（含中英混合）→ ZipVoice 离线合成
            from assistants.jarvis import tts_zipvoice
            return tts_zipvoice.synthesize(text, output_path=output_path, **kwargs)
        # 英文 → Piper (金属感后处理)
        from assistants.jarvis import tts_piper
        return tts_piper.synthesize(text, output_path=output_path, **kwargs)

    def synthesize_to_array(self, text: str, **kwargs) -> tuple[np.ndarray, int] | None:
        if self._is_chinese(text):
            from assistants.jarvis import tts_zipvoice
            return tts_zipvoice.synthesize_to_array(text, **kwargs)
        from assistants.jarvis import tts_piper
        return tts_piper.synthesize_to_array(text, **kwargs)

    def synthesize_streaming(self, text: str, stop_event: Event = None,
                             volume: float = 1.5) -> bool:
        if self._is_chinese(text):
            from assistants.jarvis import tts_zipvoice
            return tts_zipvoice.synthesize_streaming(
                text, stop_event=stop_event, volume=volume,
            )
        from assistants.jarvis import tts_piper
        return tts_piper.synthesize_streaming(
            text, stop_event=stop_event, volume=volume,
        )


class ZipVoiceTTS(AssistantTTS):
    """ZipVoice 零样本克隆后端。"""

    def __init__(self, config: dict = None):
        from assistants.jarvis import tts_zipvoice
        tts_zipvoice.configure(config or {})

    def is_available(self) -> bool:
        from assistants.jarvis import tts_zipvoice
        return tts_zipvoice.is_available()

    def synthesize(self, text: str, output_path: str = None, **kwargs) -> str | None:
        from assistants.jarvis import tts_zipvoice
        return tts_zipvoice.synthesize(text, output_path=output_path, **kwargs)

    def synthesize_to_array(self, text: str, **kwargs) -> tuple[np.ndarray, int] | None:
        from assistants.jarvis import tts_zipvoice
        return tts_zipvoice.synthesize_to_array(text, **kwargs)

    def synthesize_streaming(self, text: str, stop_event: Event = None,
                             volume: float = 1.5) -> bool:
        from assistants.jarvis import tts_zipvoice
        return tts_zipvoice.synthesize_streaming(
            text, stop_event=stop_event, volume=volume,
        )
