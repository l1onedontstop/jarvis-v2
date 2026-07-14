#!/usr/bin/env python3
"""测试麦克风 + KWS 唤醒词检测"""

import sys
import time
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_DIR / "src"))
sys.path.insert(0, str(_PROJECT_DIR / "src" / "speech"))

import sounddevice as sd
import numpy as np

print("=" * 50)
print("  贾维斯 v2 — 麦克风 + KWS 测试")
print("=" * 50)

# 1. 列出音频设备
print("\n🎤 可用音频设备:")
devices = sd.query_devices()
for i, dev in enumerate(devices):
    if dev["max_input_channels"] > 0:
        print(f"  [{i}] {dev['name']} (输入通道: {dev['max_input_channels']})")

default_input = sd.default.device[0]
print(f"\n  默认输入设备: [{default_input}] {devices[default_input]['name']}")

# 2. 测试 KWS
print("\n🔊 测试 KWS 唤醒词检测...")
try:
    import sherpa_onnx

    kws_models = list((_PROJECT_DIR / "models").glob("sherpa-onnx-kws-*"))
    if not kws_models:
        print("  ❌ 未找到 KWS 模型！")
        print("  请检查: ls ~/jarvis-v2/models/sherpa-onnx-kws-*")
    else:
        model_dir = str(kws_models[0])
        print(f"  ✅ 模型: {model_dir}")

        # 合并关键词
        keywords = ""
        kw_dir = _PROJECT_DIR / "config" / "keywords"
        for kf in sorted(kw_dir.glob("*.txt")):
            with open(kf) as f:
                keywords += f.read() + "\n"

        if keywords.strip():
            tmp_kw = "/tmp/jarvis_v2_kws_test.txt"
            with open(tmp_kw, "w") as f:
                f.write(keywords)
            print(f"  ✅ 关键词: {tmp_kw}")

            # 初始化 KWS
            model_dir_path = Path(model_dir)
            kws = sherpa_onnx.KeywordSpotter(
                tokens=str(model_dir_path / "tokens.txt"),
                encoder=str(model_dir_path / "encoder-epoch-13-avg-2-chunk-16-left-64.onnx"),
                decoder=str(model_dir_path / "decoder-epoch-13-avg-2-chunk-16-left-64.onnx"),
                joiner=str(model_dir_path / "joiner-epoch-13-avg-2-chunk-16-left-64.onnx"),
                keywords_file=tmp_kw,
                num_threads=2,
            )
            print("  ✅ KWS 初始化成功")
            print(f"\n  🎙️ 开始监听 (按 Ctrl+C 停止)...")
            print(f"  试试说: '贾维斯' 或 '林妹妹何在'")

            sample_rate = 16000
            block_size = 480
            stream = kws.create_stream()

            def callback(indata, frames, time_info, status):
                audio = indata[:, 0].copy().astype(np.float32)
                stream.accept_waveform(sample_rate, audio)
                while kws.is_ready(stream):
                    kws.decode_stream(stream)
                result = kws.get_result(stream)
                if result:
                    print(f"\n  🔊 检测到唤醒词: {result}")
                    kws.reset_stream(stream)

            try:
                with sd.InputStream(
                    channels=1,
                    samplerate=sample_rate,
                    blocksize=block_size,
                    callback=callback,
                ):
                    while True:
                        time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n  👋 测试结束")
        else:
            print("  ❌ 关键词文件为空")

except ImportError as e:
    print(f"  ❌ 导入失败: {e}")
    print("  请先: source ./venv/bin/activate")
except Exception as e:
    print(f"  ❌ 异常: {e}")
