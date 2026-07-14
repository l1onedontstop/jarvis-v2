#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Jarvis TTS — 中英双语合成

英文: Piper (金属感后处理)
中文: edge-tts 云希 (v1 同款神经网络男声)
"""

from threading import Event
import numpy as np

from assistants.tts import AssistantTTS


class JarvisTTS(AssistantTTS):

    def __init__(self, config: dict = None):
        from assistants.jarvis import tts_piper
        tts_piper.configure(config or {})

    def is_available(self) -> bool:
        return True

    def _is_chinese(self, text: str) -> bool:
        chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
        return chinese_chars > len(text.replace(' ', '')) * 0.3

    def _synth_chinese_file(self, text: str, output_path: str = None) -> str:
        """中文统一走 edge-tts → mp3"""
        import asyncio, tempfile
        path = output_path or tempfile.mktemp(suffix=".mp3")
        async def _run():
            import edge_tts
            await edge_tts.Communicate(text, "zh-CN-YunxiNeural").save(path)
        try:
            asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_run())
        return path

    # ── 核心合成接口 ────────────────────────────────────

    def synthesize(self, text: str, output_path: str = None, **kwargs) -> str | None:
        if self._is_chinese(text):
            return self._synth_chinese_file(text, output_path)
        from assistants.jarvis import tts_piper
        return tts_piper.synthesize(text, output_path=output_path, **kwargs)

    def synthesize_to_array(self, text: str, **kwargs) -> tuple[np.ndarray, int] | None:
        if self._is_chinese(text):
            import soundfile as sf
            path = self._synth_chinese_file(text)
            audio, sr = sf.read(path)
            return audio, sr
        from assistants.jarvis import tts_piper
        return tts_piper.synthesize_to_array(text, **kwargs)

    def synthesize_streaming(self, text: str, stop_event: Event = None,
                             volume: float = 1.5) -> bool:
        if self._is_chinese(text):
            import audio
            path = self._synth_chinese_file(text)
            return audio.play_audio_file(path, volume=volume)
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
