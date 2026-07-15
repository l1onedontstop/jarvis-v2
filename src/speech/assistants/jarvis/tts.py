#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Jarvis TTS — 中英双语合成

英文: Piper (金属感后处理)
中文: edge-tts 云希 (v1 同款神经网络男声)
"""

import os
import subprocess
import json
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

    def _synth_chinese_file(self, text: str, output_path: str = None) -> str | None:
        """中文：edge-tts 云希 → 超时 8s → 返回 None，调用方用 Piper 英文兜底"""
        import asyncio, tempfile, logging
        path = output_path or tempfile.mktemp(suffix=".mp3")
        try:
            asyncio.run(asyncio.wait_for(
                __import__('edge_tts').Communicate(text, "zh-CN-YunxiNeural").save(path),
                timeout=8.0
            ))
            return path
        except (asyncio.TimeoutError, RuntimeError, Exception) as e:
            logging.getLogger(__name__).warning(f"edge-tts 超时 → 切换英文")
            return None  # 返回 None 让上层用 Piper 兜底

    # ── 核心合成接口 ────────────────────────────────────

    def synthesize(self, text: str, output_path: str = None, **kwargs) -> str | None:
        if self._is_chinese(text):
            result = self._synth_chinese_file(text, output_path)
            if result is not None:
                return result
            # edge-tts 超时 → 翻译成英文 + Piper 朗读
            return self._fallback_piper(text, output_path)
        from assistants.jarvis import tts_piper
        return tts_piper.synthesize(text, output_path=output_path, **kwargs)

    def synthesize_to_array(self, text: str, **kwargs) -> tuple[np.ndarray, int] | None:
        if self._is_chinese(text):
            result = self._synth_chinese_file(text)
            if result is not None:
                import soundfile as sf
                audio, sr = sf.read(result)
                return audio, sr
            # edge-tts 超时 → 翻译成英文 + Piper 数组输出
            from assistants.jarvis import tts_piper
            prefix = "Apologies sir, Chinese speech unavailable. Here is the translation. "
            translated = self._translate_to_english(text)
            return tts_piper.synthesize_to_array(prefix + translated, **kwargs)
        from assistants.jarvis import tts_piper
        return tts_piper.synthesize_to_array(text, **kwargs)

    def synthesize_streaming(self, text: str, stop_event: Event = None,
                             volume: float = 1.5) -> bool:
        if self._is_chinese(text):
            result = self._synth_chinese_file(text)
            if result is not None:
                import audio
                return audio.play_audio_file(result, volume=volume)
            # edge-tts 超时 → 翻译成英文 + Piper 流式朗读
            from assistants.jarvis import tts_piper
            prefix = "Apologies sir, Chinese speech unavailable. Here is the translation. "
            translated = self._translate_to_english(text)
            return tts_piper.synthesize_streaming(
                prefix + translated, stop_event=stop_event, volume=volume
            )
        from assistants.jarvis import tts_piper
        return tts_piper.synthesize_streaming(
            text, stop_event=stop_event, volume=volume,
        )

    # ── 中文 TTS 超时 → 翻译成英文 + Piper 朗读 ──────────

    @staticmethod
    def _translate_to_english(text: str) -> str:
        """用 Claude CLI 做中译英（1-2s）。失败回退到本地 Ollama（15-30s）。"""
        # 方案 A: Claude CLI 快速翻译
        try:
            prompt = f"Translate to natural English. Reply with ONLY the English text, nothing else:\n\n{text}"
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", os.environ.get("CLAUDE_MODEL", "claude-sonnet-5"),
                 "--output-format", "text", "--bare", "--max-turns", "1"],
                capture_output=True, text=True, timeout=15
            )
            translation = result.stdout.strip()
            if translation and len(translation) > 3:
                return translation
        except Exception:
            pass

        # 方案 B: 本地 Ollama 兜底
        try:
            payload = json.dumps({
                "model": "minicpm-v4.6:1b",
                "prompt": f"Translate to English, reply ONLY with the translation:\n\n{text}",
                "stream": False
            })
            result = subprocess.run(
                ["curl", "-sS", "http://localhost:11434/api/generate", "-d", payload],
                capture_output=True, text=True, timeout=45
            )
            data = json.loads(result.stdout)
            translation = data.get("response", "").strip()
            subprocess.Popen(
                ["ollama", "stop", "minicpm-v4.6:1b"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return translation if translation else text
        except Exception:
            return text

    @staticmethod
    def _fallback_piper(text: str, output_path: str = None) -> str | None:
        """翻译中文 → 英文 → Piper 朗读。"""
        from assistants.jarvis import tts_piper
        prefix = "Apologies sir, the Chinese speech engine is unavailable. Here is the translation. "
        translated = JarvisTTS._translate_to_english(text)
        full_text = prefix + translated
        return tts_piper.synthesize(full_text, output_path=output_path)


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
