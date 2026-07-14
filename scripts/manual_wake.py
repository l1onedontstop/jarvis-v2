#!/usr/bin/env python3
"""手动触发唤醒 — 测试可视化 + Claude + TTS 完整链路"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/src")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/src/speech")

# 模拟唤醒流程：音效 → 视觉 → Claude → TTS
print("=== 手动触发贾维斯唤醒 ===\n")

# 1. 唤醒音效
print("1. 播放唤醒音效...")
from assistants.jarvis.feedback import JarvisFeedback
fb = JarvisFeedback()
fb.play_sound("wake")
time.sleep(0.5)

# 2. HUD 视觉特效
print("2. 发送视觉特效...")
from assistants.jarvis.visual import JarvisVisual
vis = JarvisVisual()
vis.show_wake_effect()
time.sleep(0.3)

# 3. 初始化 TTS
print("3. 初始化 TTS...")
from assistants.jarvis.tts import JarvisTTS
tts = JarvisTTS()
time.sleep(0.5)

# 4. 播放唤醒问候
print("4. 播放问候语...")
tts.speak("Reporting for duty, sir. I'm all ears.")

# 5. Claude 引擎对话
print("\n5. Claude 引擎回复...")
from claude_engine import ClaudeEngine
engine = ClaudeEngine()
chunks = []
def on_chunk(c):
    chunks.append(c)
    print(f"   {c[:60]}...")

result = engine.send_and_wait_stream(
    "你好，用一句话介绍自己",
    on_chunk=on_chunk
)

if result:
    print(f"\n6. TTS 播报回复...")
    tts.speak(result)
    print("✅ 完整链路测试完成")
else:
    print("❌ Claude 无回复")

print("\n如果你听到了音效+TTS+看到了HUD动画，说明链路是通的")
print("问题在 voice_assistant 的 KWS→唤醒 链路里")
