#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Jarvis TTS adapters."""

from threading import Event

import numpy as np

from assistants.tts import AssistantTTS


class JarvisTTS(AssistantTTS):
    """Legacy English Jarvis voice using Piper."""

    def __init__(self, config: dict = None):
        from assistants.jarvis import tts_piper
        tts_piper.configure(config or {})

    def is_available(self) -> bool:
        from assistants.jarvis import tts_piper
        return tts_piper.is_available()

    def synthesize(self, text: str, output_path: str = None, **kwargs) -> str | None:
        from assistants.jarvis import tts_piper
        return tts_piper.synthesize(text, output_path=output_path, **kwargs)

    def synthesize_to_array(self, text: str, **kwargs) -> tuple[np.ndarray, int] | None:
        from assistants.jarvis import tts_piper
        return tts_piper.synthesize_to_array(text, **kwargs)

    def synthesize_streaming(self, text: str, stop_event: Event = None,
                             volume: float = 1.5) -> bool:
        from assistants.jarvis import tts_piper
        return tts_piper.synthesize_streaming(
            text, stop_event=stop_event, volume=volume,
        )


class JarvisV2OnnxTTS(AssistantTTS):
    """Bilingual JARVIS-V2 MeloTTS model running in ONNX Runtime."""

    parallel_synthesis_workers = 1

    def __init__(self, config: dict = None):
        from assistants.jarvis import tts_melotts_onnx
        tts_melotts_onnx.configure(config or {})
        tts_melotts_onnx.preload()

    def is_available(self) -> bool:
        from assistants.jarvis import tts_melotts_onnx
        return tts_melotts_onnx.is_available()

    def synthesize(self, text: str, output_path: str = None, **kwargs):
        from assistants.jarvis import tts_melotts_onnx
        return tts_melotts_onnx.synthesize(text, output_path=output_path, **kwargs)

    def synthesize_to_array(self, text: str, **kwargs):
        from assistants.jarvis import tts_melotts_onnx
        return tts_melotts_onnx.synthesize_to_array(text, **kwargs)

    def synthesize_streaming(self, text: str, stop_event: Event = None,
                             volume: float = 1.5) -> bool:
        from assistants.jarvis import tts_melotts_onnx
        return tts_melotts_onnx.synthesize_streaming(
            text, stop_event=stop_event, volume=volume,
        )
