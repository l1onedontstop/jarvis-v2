"""
Claude Engine v2 — 持久会话智能体引擎

实现与 OpenClaw/hermes 桥接兼容的 send_and_wait_stream 接口。

关键改进：
- 用 --session-id + --resume 保持跨轮上下文（v1 的 ClaudeSession 能力）
- 用 --bare 跳过 hooks（3s 冷启动）
- 用 stream-json 流式输出（支持 TTS 句级播报 + 工具调用检测）
- 注入跨会话持久上下文（voice_context_store + history_reader）
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

# ── System Prompt — 从 SOUL.md 加载角色圣经 ─────────────────

_SOUL_PATH = _PROJECT_DIR / "prompts" / "jarvis" / "SOUL.md"
_SOUL_CACHE: str | None = None


def _load_soul() -> str:
    """加载 SOUL.md 角色圣经。缓存到内存，只读一次。"""
    global _SOUL_CACHE
    if _SOUL_CACHE is not None:
        return _SOUL_CACHE
    try:
        if _SOUL_PATH.exists():
            _SOUL_CACHE = _SOUL_PATH.read_text(encoding="utf-8").strip()
            logger.info(f"SOUL 已加载: {len(_SOUL_CACHE)} 字符")
            return _SOUL_CACHE
    except Exception as e:
        logger.warning(f"SOUL 加载失败: {e}")
    _SOUL_CACHE = ""
    return ""


def _build_system_prompt() -> str:
    """拼接完整系统提示词：SOUL 人格 + 引擎规则。"""
    soul = _load_soul()
    if soul:
        return (
            f"{soul}\n\n"
            "---\n"
            "## 引擎规则\n\n"
            "不要执行每日简报协议。\n"
            "你可以使用 Bash、WebSearch、Read、Write 等工具完成用户指令。\n"
            "回复适合语音播报，不要 markdown、列表符号、emoji。\n\n"
            "摄像头与视觉：当用户需要你看他/分析画面时，直接用 Bash 执行，不需要额外确认：\n"
            "1. TOKEN=$(cat data/.api_token) && "
            "curl -sS \"http://127.0.0.1:18790/camera/snapshot?token=$TOKEN\" "
            "-o /tmp/jarvis_cam.jpg\n"
            "2. 用 Read 工具读取 /tmp/jarvis_cam.jpg，直接分析图像内容\n"
            "3. 如果你的模型不支持图像识别，则用 bash scripts/vision_analyze.sh "
            "/tmp/jarvis_cam.jpg \"用户的问题\" 调用本地视觉模型\n"
            "4. 基于分析结果直接语音回复。以上都是预授权，一步完成，不中间问用户。"
        )
    # Fallback: SOUL 不可用时
    return (
        "你是贾维斯 (J.A.R.V.I.S.)，Luzhiyang 的 AI 智能体助手。"
        "不要执行每日简报协议。"
        "你可以使用 Bash、WebSearch、Read、Write 等工具完成用户指令。"
        "回复简洁，适合语音播报。称呼用户为\"先生\"。"
        "用户说什么语言，你就用什么语言回复。"
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
        self._history_reader = None

    def _ready_check(self) -> bool:
        return self._ready

    def precheck_async(self):
        self._ready = True

    def set_history_reader(self, reader):
        """注入跨会话持久上下文读取器。"""
        self._history_reader = reader

    # ── 上下文注入 ────────────────────────────────────────

    def _build_context(self, text: str) -> str:
        """构建注入到 Agent prompt 的持久上下文前缀。"""
        parts = []

        # 1) 近期对话（voice_context_store）
        try:
            import voice_context_store
            turns = voice_context_store.recent_turns("jarvis", limit=6)
            if turns:
                history_text = "\n".join(
                    f"{t['role']}: {t['content'][:200]}"
                    for t in turns
                )
                parts.append(
                    "# 近期对话历史（已持久化，跨会话保留）\n"
                    f"{history_text}"
                )
        except Exception:
            pass

        # 2) 长期记忆（history_reader）
        if self._history_reader:
            try:
                if self._history_reader.is_available():
                    memories = self._history_reader.search_memory(text, limit=3)
                    if memories:
                        mem_text = "\n".join(f"- {m[:200]}" for m in memories)
                        parts.append(
                            "# 相关长期记忆\n"
                            f"{mem_text}"
                        )
            except Exception:
                pass

        if not parts:
            return text

        context = "\n\n".join(parts)
        return f"{context}\n\n---\n当前用户指令: {text}"

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

        # 注入持久上下文
        prompt = self._build_context(text)

        # 构建命令
        cmd = [_CLAUDE_BIN, "-p", prompt, "--model", self.model,
               "--output-format", "stream-json", "--verbose",
               "--bare",
               "--permission-mode", "bypassPermissions",
               "--append-system-prompt", _build_system_prompt()]

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
