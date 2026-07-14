"""
Speech Pipeline — sherpa-onnx 语音管道封装

将 Assistant-X 的语音管道（KWS+ASR+TTS）封装为事件驱动的接口，
对接 v2 的 StateMachine + QuickActions + ClaudeBridge。

事件流：
  麦克风 → VAD → KWS(唤醒词) → 活体检测 → 声纹验证
    → ASR(识别) → 回调 on_asr_result(text)
    → 主循环处理 → TTS 播报
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
_MODELS_DIR = _PROJECT_DIR / "models"


class SpeechPipeline:
    """
    语音管道封装。

    用法:
        pipeline = SpeechPipeline()
        pipeline.on_wake = lambda role: print(f"唤醒: {role}")
        pipeline.on_asr_result = lambda text: print(f"识别: {text}")
        pipeline.start()
        # ... 运行中 ...
        pipeline.speak("你好先生")
        pipeline.stop()
    """

    def __init__(
        self,
        models_dir: str = "",
        role: str = "jarvis",
        asr_mode: str = "offline",  # offline / streaming
        tts_engine: str = "piper",  # piper / vits / macos_say
    ):
        self._models_dir = Path(models_dir) if models_dir else _MODELS_DIR
        self._role = role
        self._asr_mode = asr_mode
        self._tts_engine = tts_engine
        self._running = False

        # 事件回调
        self.on_wake = None              # callable(role: str)
        self.on_wake_rejected = None     # callable(reason: str)
        self.on_asr_partial = None       # callable(text: str)
        self.on_asr_final = None         # callable(text: str)
        self.on_silence_timeout = None   # callable()
        self.on_status = None            # callable(state: str)

        # 内部组件（延迟初始化）
        self._kws = None
        self._asr = None
        self._vad = None
        self._tts = None
        self._audio_thread: threading.Thread | None = None
        self._speak_queue = queue.Queue()

    # ── 生命周期 ──────────────────────────────────────────

    def start(self):
        """启动语音管道（非阻塞，在后台线程运行音频循环）"""
        self._running = True

        # 初始化组件
        self._init_components()

        # 启动音频线程
        self._audio_thread = threading.Thread(
            target=self._audio_loop, name="jarvis-audio", daemon=True
        )
        self._audio_thread.start()
        logger.info("🎤 语音管道已启动")

    def stop(self):
        """停止语音管道"""
        self._running = False
        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=3)
        logger.info("🔇 语音管道已停止")

    # ── 组件初始化 ────────────────────────────────────────

    def _init_components(self):
        """初始化 sherpa-onnx 组件"""
        try:
            import sherpa_onnx
        except ImportError:
            logger.error("sherpa-onnx 未安装！")
            raise

        # KWS（唤醒词检测）
        self._init_kws()

        # ASR（语音识别）
        self._init_asr()

        # TTS（语音合成）
        self._init_tts()

        logger.info("sherpa-onnx 组件初始化完成")

    def _init_kws(self):
        """初始化关键词检测器"""
        import sherpa_onnx

        kws_models = list(self._models_dir.glob("sherpa-onnx-kws-*"))
        if not kws_models:
            logger.warning("未找到 KWS 模型，跳过唤醒词检测")
            return

        model_dir = str(kws_models[0])

        # 合并关键词文件
        keywords_dir = _PROJECT_DIR / "config" / "keywords"
        keywords_files = list(keywords_dir.glob("*.txt"))
        merged_keywords = ""
        for kf in keywords_files:
            with open(kf, "r", encoding="utf-8") as f:
                merged_keywords += f.read() + "\n"

        if not merged_keywords.strip():
            logger.warning("关键词文件为空，KWS 无法初始化")
            return

        tmp_keywords = "/tmp/jarvis_v2_keywords.txt"
        with open(tmp_keywords, "w", encoding="utf-8") as f:
            f.write(merged_keywords)

        try:
            self._kws = sherpa_onnx.KeywordSpotter(
                tokens=str(tmp_keywords),
                model=model_dir,
                num_threads=2,
            )
            logger.info("KWS 初始化完成")
        except Exception as e:
            logger.error(f"KWS 初始化失败: {e}")

    def _init_asr(self):
        """初始化语音识别器"""
        import sherpa_onnx

        # 优先使用 SenseVoice（离线模式）
        sense_voice_models = list(self._models_dir.glob("sherpa-onnx-sense-voice-*"))
        if sense_voice_models:
            try:
                model_dir = str(sense_voice_models[0])
                self._asr = sherpa_onnx.OfflineRecognizer(
                    model=model_dir,
                    num_threads=2,
                )
                logger.info("ASR (SenseVoice 离线) 初始化完成")
                return
            except Exception as e:
                logger.warning(f"SenseVoice 初始化失败: {e}")

        # 回退：流式识别
        streaming_models = list(self._models_dir.glob("sherpa-onnx-streaming-zipformer-*"))
        if streaming_models:
            try:
                from sherpa_onnx import OnlineRecognizer, OnlineStream
                recognizer = OnlineRecognizer(
                    model=str(streaming_models[0]),
                    decoding_method="greedy_search",
                    num_threads=2,
                )
                self._asr = recognizer
                logger.info("ASR (Zipformer 流式) 初始化完成")
            except Exception as e:
                logger.error(f"流式 ASR 初始化失败: {e}")

    def _init_tts(self):
        """初始化 TTS 引擎"""
        # Phase 1: 使用 macOS say 作为默认 TTS
        import platform
        if platform.system() == "Darwin":
            self._tts = "macos_say"
            logger.info("TTS: macOS say")
        else:
            self._tts = None
            logger.warning("TTS 不可用（非 macOS）")

    # ── 音频循环 ──────────────────────────────────────────

    def _audio_loop(self):
        """音频采集和处理主循环（在后台线程运行）"""
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            logger.error("sounddevice / numpy 未安装")
            return

        sample_rate = 16000
        block_size = 480  # 10ms @ 16kHz

        def audio_callback(indata, frames, time_info, status):
            if not self._running:
                raise sd.CallbackStop

            audio = indata[:, 0].copy()  # 单声道

            # KWS 检测
            if self._kws is not None:
                try:
                    result = self._kws.accept_waveform(sample_rate, audio)
                    if result and self.on_wake:
                        logger.info(f"🔊 KWS 命中: {result}")
                        # 在事件循环中调用回调
                        asyncio.run_coroutine_threadsafe(
                            self._async_emit("wake", result),
                            asyncio.get_event_loop()
                        )
                except Exception:
                    pass

            # VAD + ASR 检测
            if self._asr is not None:
                # SenseVoice (offline): 缓冲后整句识别
                if hasattr(self._asr, "decode"):
                    try:
                        result = self._asr.decode(audio, sample_rate)
                        if result and result.text.strip() and self.on_asr_final:
                            asyncio.run_coroutine_threadsafe(
                                self._async_emit("asr", result.text),
                                asyncio.get_event_loop()
                            )
                    except Exception:
                        pass

        try:
            with sd.InputStream(
                channels=1,
                samplerate=sample_rate,
                blocksize=block_size,
                callback=audio_callback,
                device=None,
            ):
                while self._running:
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"音频循环异常: {e}")

    # ── TTS ────────────────────────────────────────────────

    def speak(self, text: str):
        """TTS 播报文本"""
        if not text or not self._tts:
            return

        if self._tts == "macos_say":
            import subprocess
            try:
                subprocess.Popen(
                    ["say", "-v", "Lee", text],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception as e:
                logger.warning(f"TTS 失败: {e}")

    def stop_speaking(self):
        """停止当前 TTS"""
        import subprocess
        subprocess.run(["killall", "say"], capture_output=True)

    # ── 辅助 ──────────────────────────────────────────────

    async def _async_emit(self, event_type: str, data: str):
        """在事件循环中安全地触发回调"""
        try:
            if event_type == "wake":
                # 解析唤醒角色
                role = "jarvis"
                if "林妹妹" in data:
                    role = "lin-meimei"
                if self.on_wake:
                    self.on_wake(role)
            elif event_type == "asr":
                if self.on_asr_final:
                    self.on_asr_final(data)
        except Exception as e:
            logger.error(f"回调异常: {e}")


# ── 工厂函数 ──────────────────────────────────────────────

_pipeline: SpeechPipeline | None = None


def get_speech_pipeline() -> SpeechPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = SpeechPipeline()
    return _pipeline
