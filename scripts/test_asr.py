#!/usr/bin/env python3
"""测试 ASR 语音识别 — 说一句话自动识别"""

import sys
import time
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent

import sounddevice as sd
import numpy as np
import sherpa_onnx

print("🎙️ ASR 测试 — 说一句话，说完等 2 秒自动识别")

models_dir = _PROJECT_DIR / "models"
sense_voice = list(models_dir.glob("sherpa-onnx-sense-voice-*"))

if not sense_voice:
    print("❌ 未找到 SenseVoice 模型")
    sys.exit(1)

model_dir = sense_voice[0]
# SenseVoice 模型的 tokens 在模型目录里
tokens_file = model_dir / "tokens.txt"
if not tokens_file.exists():
    # 尝试看看目录里有什么
    print(f"模型目录: {model_dir}")
    for f in model_dir.iterdir():
        print(f"  {f.name}")
    sys.exit(1)

print(f"  模型: {model_dir.name}")
print(f"  Tokens: {tokens_file}")

# 用 SenseVoice 工厂方法
# SenseVoice 模型：需要 .onnx 文件，不是目录
model_file = model_dir / "model.int8.onnx"
print(f"  模型文件: {model_file}")

asr = sherpa_onnx.offline_recognizer.OfflineRecognizer.from_sense_voice(
    model=str(model_file),
    tokens=str(tokens_file),
    num_threads=2,
    use_itn=True,
    language="auto",
)

# VAD 配置
vad_model = models_dir / "silero_vad.onnx"
vad_config = None
if vad_model.exists():
    vad_config = sherpa_onnx.VadModelConfig()
    vad_config.silero_vad.model = str(vad_model)
    vad_config.silero_vad.threshold = 0.5
    vad_config.silero_vad.min_silence_duration = 0.25
    vad_config.silero_vad.min_speech_duration = 0.25
    vad_config.sample_rate = 16000
    print(f"  VAD: Silero V5 已加载")
else:
    print(f"  ⚠️ VAD 模型未找到，使用简单静音检测")

# 录音循环
sample_rate = 16000
buffer = []

def callback(indata, frames, time_info, status):
    buffer.append(indata[:, 0].copy())

print("\n🎤 开始说话... (按 Ctrl+C 停止)\n")

try:
    with sd.InputStream(channels=1, samplerate=sample_rate, blocksize=480, callback=callback):
        last_speech = time.time()
        while True:
            time.sleep(0.3)
            if len(buffer) > 0:
                last_speech = time.time()
            elif time.time() - last_speech > 2.0 and len(buffer) > 15:
                audio = np.concatenate(buffer)
                buffer.clear()

                # 创建识别流
                stream = asr.create_stream()
                stream.accept_waveform(sample_rate, audio)
                stream.input_finished()
                asr.decode_stream(stream)
                result = asr.get_result(stream)
                text = result.text.strip()
                if text:
                    print(f"  📝 {text}")
                last_speech = time.time()

except KeyboardInterrupt:
    print("\n👋 测试结束")
