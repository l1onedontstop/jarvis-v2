"""
Fast Path — Claude Haiku 秒回分流

简单问候、确认、感谢等轻量意图走 Haiku，秒级响应。
复杂任务走主 Claude 引擎（Sonnet/Opus）。

接口与朋友项目的 FastPathClient 兼容，drop-in 替换。
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading

logger = logging.getLogger(__name__)

_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
_FAST_MODEL = os.environ.get("CLAUDE_FAST_MODEL", "claude-haiku-4-5-20251001")

_VOICE_SYSTEM_PROMPT = (
    "你是贾维斯 (J.A.R.V.I.S.)，Luzhiyang 的 AI 语音助手。"
    "不要执行每日简报协议。"
    "直接、简洁地回答。1-2 句即可。称呼用户为\"先生\"。"
)

# 分句正则
_SENTENCE_SEP = re.compile(r"[。！？\n]")


class FastPathClaude:
    """Claude Haiku 快路径客户端"""

    def __init__(self, should_stop=None, agent_name: str = "jarvis", agent_id: str = "jarvis"):
        self.model = _FAST_MODEL
        self._should_stop = should_stop  # threading.Event
        self._agent_name = agent_name
        self._agent_id = agent_id
        self._persona = ""
        self._history_reader = None

    def is_available(self) -> bool:
        return True  # Claude CLI 始终可用

    def set_persona(self, persona: str):
        self._persona = persona

    def set_history_reader(self, reader):
        self._history_reader = reader

    def send_and_wait_stream(
        self, text: str,
        on_chunk=None, on_start=None, on_end=None, on_tool_call=None
    ):
        """
        用 Haiku 快速回复，流式推送
        """
        if not text or not text.strip():
            return None

        logger.info(f"FastPath(Haiku): {text[:60]}...")

        prompt = text
        if self._persona:
            prompt = f"[角色: {self._persona}]\n\n用户: {text}"

        try:
            proc = subprocess.Popen(
                [_CLAUDE_BIN, "-p", prompt, "--model", self.model,
                 "--output-format", "text",
                 "--bare",
                 "--append-system-prompt", _VOICE_SYSTEM_PROMPT],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            full_text = ""
            started = False

            for line in iter(proc.stdout.readline, ""):
                if self._should_stop and self._should_stop.is_set():
                    proc.terminate()
                    break

                line = line.strip()
                if not line:
                    continue

                if not started:
                    started = True
                    if on_start:
                        try:
                            on_start()
                        except Exception:
                            pass

                full_text += line + "\n"
                if on_chunk:
                    try:
                        on_chunk(line)
                    except Exception:
                        pass

            proc.wait(timeout=30)

            result = full_text.strip()
            if on_end:
                try:
                    on_end(result)
                except Exception:
                    pass

            return result

        except Exception as e:
            logger.error(f"FastPath 失败: {e}")
            # 抛 AgentHandoff 让主引擎兜底
            raise AgentHandoff(task=text, original_text=text, reason=f"error:{e}")


class AgentHandoff(Exception):
    """快路径失败 → 交给主引擎"""

    def __init__(self, task, original_text, reason="model"):
        super().__init__(f"handoff({reason}): {task[:60]}")
        self.task = task
        self.original_text = original_text
        self.reason = reason
