"""
Claude Engine — 伪装成 OpenClaw/Hermes 桥接，实际调用 Claude Code

实现朋友项目期望的 send_and_wait_stream 接口，
这样朋友的语音管道不用改，只换后端。
"""

from __future__ import annotations

import asyncio
import logging
import os
import queue
import re
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent

# 语音助手 System Prompt — 覆盖全局每日简报协议
_VOICE_SYSTEM_PROMPT = (
    "你是贾维斯 (J.A.R.V.I.S.)，Luzhiyang 的 AI 语音助手。"
    "不要执行每日简报协议，不要读提醒事项或项目文件。"
    "直接、简洁地回答用户问题。回复控制在 2-3 句，适合语音播报。"
    "称呼用户为\"先生\"。使用中文回复。"
)

# 中文分句正则 — 用于流式推送
_SENTENCE_SEP = re.compile(r"[。！？\n]")


class ClaudeEngine:
    """模拟 OpenClawBridge 接口的 Claude Code 引擎"""

    def __init__(self, **kwargs):
        self.model = _MODEL
        self._ready = True
        self._aborted = False
        self._lock = threading.Lock()

    def _ready_check(self) -> bool:
        return self._ready

    def precheck_async(self):
        """异步连通性检测 — Claude Code 无持久连接，直接标记就绪"""
        self._ready = True

    # ── 核心接口（与 OpenClaw/hermes 桥接同签名）─────────────

    def send_and_wait_stream(
        self, text: str,
        on_chunk=None,
        on_start=None,
        on_end=None,
        on_tool_call=None,
    ):
        """
        发送消息并流式返回。回调约定：
          - on_start() → 模型开始输出
          - on_chunk(text) → 每次收到新文本片段
          - on_end(full_text) → 输出结束
          - on_tool_call(name, args) → 工具调用
        """
        if not text or not text.strip():
            return None

        logger.info(f"Claude 请求: {text[:60]}...")
        self._aborted = False

        try:
            proc = subprocess.Popen(
                [_CLAUDE_BIN, "-p", text,
                 "--model", self.model,
                 "--output-format", "text",
                 "--bare",
                 "--append-system-prompt", _VOICE_SYSTEM_PROMPT],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=_PROJECT_DIR,
                text=True,
            )

            full_text = ""
            started = False

            # 逐行读取 Claude 输出
            for line in iter(proc.stdout.readline, ""):
                if self._aborted:
                    proc.terminate()
                    break

                if not line.strip():
                    continue

                if not started:
                    started = True
                    if on_start:
                        try:
                            on_start()
                        except Exception:
                            pass

                full_text += line

                # 按句推送（模拟流式）
                if on_chunk:
                    try:
                        on_chunk(line.strip())
                    except Exception:
                        pass

            proc.wait(timeout=30)

            if on_end:
                try:
                    on_end(full_text.strip())
                except Exception:
                    pass

            logger.info(f"Claude 回复: {full_text[:80]}...")
            return full_text.strip()

        except Exception as e:
            logger.error(f"Claude 调用失败: {e}")
            if on_end:
                try:
                    on_end("")
                except Exception:
                    pass
            return None

    def abort(self):
        """中断当前请求"""
        self._aborted = True

    def send_stop_command(self):
        """软停止（不断开会话）"""
        self._aborted = True

    def cancel_task(self):
        """取消当前任务"""
        self._aborted = True

    def send_clear_command(self):
        """清除上下文"""
        pass


# ── 工厂函数（与朋友项目 get_bridge 同签名）─────────────────

_engine: ClaudeEngine | None = None


def get_bridge(**kwargs) -> ClaudeEngine:
    global _engine
    if _engine is None:
        _engine = ClaudeEngine(**kwargs)
    return _engine
