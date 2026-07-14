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

logger = logging.getLogger("jarvis")


class JarvisV2:
    """贾维斯 v2 主控制器"""

    def __init__(self):
        self.state = get_state_machine()
        self.qa = get_quick_actions()
        self.executor = get_action_executor()
        self.claude = ClaudeBridge()

        # 回调连接
        self.qa.on_step_aside = self._on_step_aside
        self.qa.on_send_wechat = self._on_send_wechat

        # 语音管道组件（延迟初始化）
        self._asr_recognizer = None
        self._kws_detector = None
        self._tts_engine = None

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

        # 初始化语音管道
        await self._init_speech_pipeline()

        # 播报就绪
        greeting = self._pick_greeting()
        await self._speak(greeting)

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
        """主交互循环。Phase 1 先以文本输入模式运行。"""
        logger.info("进入交互循环（输入 'q' 退出，输入文字模拟语音输入）")
        print("\n" + "=" * 50)
        print("  贾维斯 v2 — CLI 模式")
        print("  输入文字开始对话，输入 q 退出")
        print("=" * 50 + "\n")

        while self._running:
            try:
                user_input = await self._get_input()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue
            if user_input.lower() in ("q", "quit", "exit"):
                break

            await self._process_input(user_input)

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
        """TTS 播报（Phase 1：直接 print，后续接入 Piper）"""
        if not text:
            return
        self.state.start_speaking()
        # TODO: Phase 2 接入 TTS 管道
        self.state.finish_speaking()

    # ── 唤醒 ───────────────────────────────────────────────

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
        """微信发送回调（Phase 2 实现）"""
        logger.info(f"  💬 微信 → {contact}: {message[:30]}...")


# ── 入口 ──────────────────────────────────────────────────

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


async def main():
    setup_logging()
    jarvis = JarvisV2()

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
