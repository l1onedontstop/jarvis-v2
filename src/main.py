#!/usr/bin/env python3
"""
贾维斯 v2 — 主入口

语音管道 (sherpa-onnx) + QuickActions + Claude Code 引擎。
基于 Assistant-X 的音频管道，替换 LLM 后端为 Claude Code。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

# 确保项目根在 path
_PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_DIR / "src"))
sys.path.insert(0, str(_PROJECT_DIR / "src" / "speech"))

from state_machine import StateMachine, get_state_machine, MainState, InteractionStatus
from intelligence.quick_actions import QuickActions, ActionExecutor, get_quick_actions, get_action_executor
from intelligence.claude_bridge import ClaudeBridge
from speech.speech_pipeline import SpeechPipeline, get_speech_pipeline

logger = logging.getLogger("jarvis")


class JarvisV2:
    """贾维斯 v2 主控制器"""

    def __init__(self, cli_mode: bool = False):
        self.state = get_state_machine()
        self.qa = get_quick_actions()
        self.executor = get_action_executor()
        self.claude = ClaudeBridge()
        self.speech = get_speech_pipeline()
        self._cli_mode = cli_mode

        # 回调连接
        self.qa.on_step_aside = self._on_step_aside
        self.qa.on_send_wechat = self._on_send_wechat

        # 语音管道事件连接
        self.speech.on_wake = self._on_wake
        self.speech.on_asr_final = self._on_asr_final
        self.speech.on_silence_timeout = self._on_silence_timeout

        # 运行状态
        self._running = False
        self._current_text = ""

        # 加载配置
        self._config = self._load_config()

    # ── 配置 ──────────────────────────────────────────────

    def _load_config(self) -> dict:
        cfg_path = _PROJECT_DIR / "config" / "assistants.json"
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"default": "jarvis", "engine": "claude-code"}

    @property
    def active_role(self) -> str:
        return self._config.get("default", "jarvis")

    # ── 生命周期 ──────────────────────────────────────────

    async def start(self):
        """启动贾维斯"""
        logger.info("⚡ J.A.R.V.I.S. v2 启动中...")
        self._running = True

        if not self._cli_mode:
            # 语音模式：启动音频管道
            self.speech.start()
            greeting = self._pick_greeting()
            self.speech.speak(greeting)

        # 进入主循环
        await self._main_loop()

    async def stop(self):
        """优雅关闭"""
        logger.info("🛑 正在关闭...")
        self._running = False

    # ── 语音管道初始化 ────────────────────────────────────

    async def _init_speech_pipeline(self):
        """初始化 KWS + ASR + TTS（从朋友项目移植）"""
        try:
            import sherpa_onnx
            logger.info(f"sherpa-onnx 版本: {sherpa_onnx.__version__}")
        except ImportError as e:
            logger.error(f"sherpa-onnx 未安装: {e}")
            raise

        # 模型路径（通过 symlink 指向 ~/assistant-x-openclaw/models）
        models_dir = _PROJECT_DIR / "models"
        logger.info(f"模型目录: {models_dir}")

        # TODO: 完整初始化 KWS/ASR/TTS
        # Phase 1 先以 CLI 文本模式运行，语音管道逐步接入
        logger.info("语音管道就绪（CLI 模式）")

    # ── 主循环 ────────────────────────────────────────────

    async def _main_loop(self):
        """主交互循环。语音模式或 CLI 模式。"""
        if self._cli_mode:
            logger.info("进入交互循环（输入 'q' 退出，输入文字模拟语音输入）")
            print("\n" + "=" * 50)
            print("  贾维斯 v2 — CLI 模式")
            print("  输入文字开始对话，输入 q 退出")
            print("=" * 50 + "\n")

        while self._running:
            if self._cli_mode:
                # CLI 模式：从 stdin 读取
                try:
                    loop = asyncio.get_event_loop()
                    user_input = await loop.run_in_executor(None, sys.stdin.readline)
                except (EOFError, KeyboardInterrupt):
                    break
                if not user_input:
                    continue
                user_input = user_input.strip()
                if user_input.lower() in ("q", "quit", "exit"):
                    break
                if user_input:
                    await self._process_input(user_input)
            else:
                # 语音模式：等待事件回调
                # 检查超时
                if self.state.check_idle_timeout():
                    pass
                await asyncio.sleep(0.5)

        await self.stop()

    async def _get_input(self) -> str:
        """获取用户输入（CLI 模式：stdin）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sys.stdin.readline)

    # ── 输入处理流水线 ────────────────────────────────────

    async def _process_input(self, text: str):
        """处理用户输入：QuickActions → FastPath → Claude"""
        text = text.strip()
        if not text:
            return

        logger.info(f"📝 用户: {text}")
        self.state.wake()
        self.state.touch()

        # 1) QuickActions 匹配
        action = self.qa.match(text)
        if action and action.get("action") not in ("search_web",):
            result = self.executor.execute(action)
            if action["action"] in ("standby", "marker_step_aside"):
                self.state.standby()
                return
            if result:
                print(f"  ⚡ QuickAction: {result}")
                await self._speak(result)
                self.state.finish_speaking()
                return

        # 2) 进入处理状态
        self.state.start_processing()
        print(f"  🤔 思考中...")

        try:
            sentences = await self.claude.chat_stream(text)
            if sentences:
                response = "".join(sentences)
                print(f"  💬 {response}")
                await self._speak(response)
            else:
                print(f"  ⚠️ 空回复")
        except Exception as e:
            logger.error(f"Claude 调用失败: {e}")
            await self._speak("抱歉，我暂时无法处理这个请求。")

        self.state.finish_speaking()

    # ── TTS ────────────────────────────────────────────────

    async def _speak(self, text: str):
        """TTS 播报"""
        if not text:
            return
        self.state.start_speaking()
        self.speech.speak(text)
        self.state.finish_speaking()

    # ── 语音管道回调 ──────────────────────────────────────

    def _on_wake(self, role: str):
        """语音唤醒回调"""
        logger.info(f"🔊 语音唤醒: {role}")
        self.state.wake(role)
        # 播报问候语（在新线程避免阻塞音频回调）
        greeting = self._pick_greeting()
        if greeting:
            self.speech.speak(greeting)
        # 触发一轮输入等待
        asyncio.ensure_future(self._wake_handler())

    async def _wake_handler(self):
        """唤醒后的处理：等待用户语音输入"""
        # 此时 state 已经进入 AWAKE_LISTENING
        # ASR 结果由 _on_asr_final 处理
        pass

    def _on_asr_final(self, text: str):
        """ASR 识别完成回调"""
        text = text.strip()
        if not text:
            return
        logger.info(f"📝 ASR: {text}")
        self.state.touch()
        asyncio.ensure_future(self._process_input(text))

    def _on_silence_timeout(self):
        """静音超时回调"""
        logger.info("🔇 静音超时，返回待机")
        self.state.standby(reason="silence_timeout")

    # ── 唤醒问候 ───────────────────────────────────────────

    def _pick_greeting(self) -> str:
        """选择唤醒问候语"""
        greetings = self._config.get("assistants", [])
        for a in greetings:
            if a.get("id") == self.active_role:
                lines = a.get("wake_lines", [])
                if lines:
                    import random
                    return random.choice(lines)
        return "Reporting for duty, sir."

    # ── 回调 ──────────────────────────────────────────────

    def _on_step_aside(self, mode: str):
        """QuickAction/Marker 触发的待机"""
        logger.info(f"  🛏️ step_aside: {mode}")
        self.state.standby()

    def _on_send_wechat(self, contact: str, message: str):
        """微信发送回调"""
        logger.info(f"  💬 微信 → {contact}: {message[:30]}...")


# ── 入口 ──────────────────────────────────────────────────

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="贾维斯 v2")
    parser.add_argument("--cli", action="store_true", help="CLI 文本输入模式（默认：语音模式）")
    args = parser.parse_args()

    setup_logging()
    jarvis = JarvisV2(cli_mode=args.cli)

    # 信号处理
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.ensure_future(jarvis.stop()))
        except NotImplementedError:
            pass

    await jarvis.start()


if __name__ == "__main__":
    asyncio.run(main())
