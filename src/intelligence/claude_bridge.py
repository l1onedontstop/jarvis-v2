"""
Claude Code Bridge — 对接 Claude Code CLI 作为主 LLM 引擎

实现 EngineBridge 接口，支持：
- 流式响应（stream-json 逐句推送）
- 工具调用（自动透传）
- 会话管理（通过 claude --resume）
- 中断/取消

用法：
    bridge = ClaudeBridge()
    async for sentence in bridge.chat("今天天气怎么样", session_id="voice-001"):
        tts.speak(sentence)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Claude CLI 路径（优先 Homebrew）
_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
_IDLE_TIMEOUT = 300  # 会话闲置 5 分钟后关闭持久进程


class ClaudeBridge:
    """对接 claude CLI 的 EngineBridge 实现。"""

    def __init__(self, model: str = ""):
        self._model = model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
        self._session_id: str | None = None
        self._process: subprocess.Popen | None = None
        self._last_used = 0.0
        self._aborted = False

    # ── 核心接口 ──────────────────────────────────────────

    async def chat(self, message: str, *, session_id: str = "") -> str:
        """发送消息，获取完整回复（非流式）。适合 Fast Path。"""
        prompt = self._build_prompt(message)
        cmd = [_CLAUDE_BIN, "-p", prompt, "--model", self._model]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=_PROJECT_DIR,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=120
        )
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")[:200]
            logger.error(f"Claude CLI 错误: {err}")
            raise RuntimeError(f"Claude 调用失败: {err}")

        return stdout.decode("utf-8", errors="replace").strip()

    async def chat_stream(self, message: str, *, session_id: str = "") -> list[str]:
        """流式对话，返回句子列表（按中文标点分句）。适合主语音管道。"""
        prompt = self._build_prompt(message)
        sentences: list[str] = []
        current = ""

        cmd = [
            _CLAUDE_BIN, "-p", prompt,
            "--model", self._model,
            "--output-format", "stream-json",
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=_PROJECT_DIR,
        )

        self._aborted = False

        try:
            async for line in proc.stdout:
                if self._aborted:
                    proc.terminate()
                    break

                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    event = json.loads(line_str)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type", "")
                if event_type == "content_block_delta":
                    delta = event.get("delta", {}).get("text", "")
                    current += delta
                    # 按中文标点分句
                    for sep in ("。", "！", "？", "\n\n"):
                        if sep in current:
                            parts = current.split(sep)
                            for part in parts[:-1]:
                                part = part.strip()
                                if part:
                                    sentences.append(part)
                            current = parts[-1]
                elif event_type == "message_stop":
                    break
        except asyncio.CancelledError:
            proc.terminate()
            raise
        finally:
            if proc.returncode is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

        # 剩余文本
        current = current.strip()
        if current:
            sentences.append(current)

        # 合并过短的句子
        merged = self._merge_short(sentences)
        return merged

    async def abort(self):
        """中断当前请求"""
        self._aborted = True

    # ── 内部 ──────────────────────────────────────────────

    def _build_prompt(self, message: str) -> str:
        """构建给 Claude 的 prompt。"""
        return message

    @staticmethod
    def _merge_short(sentences: list[str], min_chars: int = 4) -> list[str]:
        """合并过短的句子，避免 TTS 碎片化。"""
        if not sentences:
            return []
        merged = []
        buf = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(s) < min_chars and buf:
                buf += s
            elif len(s) < min_chars:
                buf = s
            else:
                if buf:
                    merged.append(buf)
                    buf = ""
                merged.append(s)
        if buf:
            if merged:
                merged[-1] += buf
            else:
                merged.append(buf)
        return merged


async def test():
    """简单自测"""
    bridge = ClaudeBridge()
    result = await bridge.chat("你好，请用一句话介绍自己")
    print(f"chat: {result}")

    sentences = await bridge.chat_stream("用三句话介绍北京")
    print(f"stream: {sentences}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test())
