"""
Claude Code Bridge v2 — 对接 Claude Code CLI

用法:
    bridge = ClaudeBridge()
    reply = await bridge.chat("今天天气怎么样")
    sentences = await bridge.chat_stream("用三句话介绍北京")  # 按句分割
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent

# 中文分句正则
_SENTENCE_SEP = re.compile(r"[。！？\n]")


class ClaudeBridge:
    """对接 claude CLI 的轻量桥接"""

    def __init__(self, model: str = ""):
        self.model = model or _MODEL

    async def chat(self, message: str) -> str:
        """发送消息，返回完整回复"""
        try:
            proc = await asyncio.create_subprocess_exec(
                _CLAUDE_BIN, "-p", message,
                "--model", self.model,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=_PROJECT_DIR,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120
            )
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace")[:300]
                logger.error(f"Claude 错误: {err}")
                return ""

            return stdout.decode("utf-8", errors="replace").strip()

        except asyncio.TimeoutError:
            logger.error("Claude 调用超时")
            return ""
        except Exception as e:
            logger.error(f"Claude 调用异常: {e}")
            return ""

    async def chat_stream(self, message: str) -> list[str]:
        """发送消息，返回分句列表（供 TTS 逐句播放）"""
        text = await self.chat(message)
        if not text:
            return []

        # 按中文标点分句
        parts = _SENTENCE_SEP.split(text)
        sentences = [p.strip() for p in parts if p.strip()]
        return self._merge_short(sentences)

    @staticmethod
    def _merge_short(sentences: list[str], min_chars: int = 4) -> list[str]:
        """合并过短句子，避免 TTS 碎片化"""
        if not sentences:
            return []
        merged = []
        buf = ""
        for s in sentences:
            if len(s) < min_chars:
                buf += s
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
