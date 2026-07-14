"""
Claude Engine v2 — 持久会话智能体引擎

实现与 OpenClaw/hermes 桥接兼容的 send_and_wait_stream 接口。

关键改进：
- 用 --session-id + --resume 保持跨轮上下文（v1 的 ClaudeSession 能力）
- 用 --bare 跳过 hooks（3s 冷启动）
- 用 stream-json 流式输出（支持 TTS 句级播报 + 工具调用检测）
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent

# 语音助手 System Prompt
_VOICE_SYSTEM_PROMPT = (
    "你是贾维斯 (J.A.R.V.I.S.)，Luzhiyang 的 AI 智能体助手。"
    "不要执行每日简报协议。"
    "你可以使用 Bash、WebSearch、Read、Write 等工具完成用户指令。"
    "回复简洁，适合语音播报。称呼用户为\"先生\"。中文回复。"
)


class ClaudeEngine:
    """持久会话 Claude 智能体引擎"""

    def __init__(self, **kwargs):
        self.model = _MODEL
        self._ready = True
        self._aborted = False
        self._lock = threading.Lock()
        self._session_id: str | None = None
        self._call_count = 0

    def _ready_check(self) -> bool:
        return self._ready

    def precheck_async(self):
        self._ready = True

    # ── 核心接口 ──────────────────────────────────────────

    def send_and_wait_stream(
        self, text: str,
        on_chunk=None,
        on_start=None,
        on_end=None,
        on_tool_call=None,
        force_agent_reason: str = "",
    ):
        """
        发送消息，流式返回。
        回调约定与 OpenClawBridge 相同。
        """
        if not text or not text.strip():
            return None

        self._aborted = False
        self._call_count += 1

        logger.info(f"Claude 会话 #{self._call_count}: {text[:60]}...")

        # 构建命令
        cmd = [_CLAUDE_BIN, "-p", text, "--model", self.model,
               "--output-format", "stream-json", "--verbose",
               "--bare",
               "--append-system-prompt", _VOICE_SYSTEM_PROMPT]

        # 持久会话
        if self._session_id and self._call_count > 1:
            cmd += ["--resume", self._session_id]
        else:
            self._session_id = str(uuid.uuid4())
            cmd += ["--session-id", self._session_id]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=_PROJECT_DIR,
                text=True,
            )

            full_text_parts = []
            started = False

            for line in iter(proc.stdout.readline, ""):
                if self._aborted:
                    proc.terminate()
                    break

                line = line.strip()
                if not line:
                    continue

                # 解析 stream-json
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type", "")

                # 跳过系统事件
                if event_type == "system":
                    continue

                # assistant 消息
                if event_type == "assistant":
                    msg = event.get("message", {})
                    contents = msg.get("content", [])

                    for block in contents:
                        block_type = block.get("type", "")
                        text_content = block.get("text", "")
                        thinking_content = block.get("thinking", "")

                        if text_content:
                            full_text_parts.append(text_content)

                            if not started:
                                started = True
                                if on_start:
                                    try:
                                        on_start()
                                    except Exception:
                                        pass

                            if on_chunk:
                                try:
                                    on_chunk(text_content)
                                except Exception:
                                    pass

                        if block_type == "tool_use":
                            if on_tool_call:
                                try:
                                    on_tool_call(
                                        block.get("name", ""),
                                        block.get("input", {})
                                    )
                                except Exception:
                                    pass

            proc.wait(timeout=60)

            full_text = "".join(full_text_parts).strip()

            if on_end:
                try:
                    on_end(full_text)
                except Exception:
                    pass

            return full_text

        except Exception as e:
            logger.error(f"Claude 调用失败: {e}")
            if on_end:
                try:
                    on_end("")
                except Exception:
                    pass
            # 重置会话（下次重新创建）
            self._session_id = None
            return None

    def abort(self):
        self._aborted = True

    def send_stop_command(self):
        self._aborted = True

    def cancel_task(self):
        self._aborted = True

    def send_clear_command(self):
        """清除会话上下文"""
        self._session_id = None
        self._call_count = 0


# ── 工厂函数 ──────────────────────────────────────────────

_engine: ClaudeEngine | None = None


def get_bridge(**kwargs) -> ClaudeEngine:
    global _engine
    if _engine is None:
        _engine = ClaudeEngine(**kwargs)
    return _engine
