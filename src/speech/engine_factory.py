#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
引擎工厂：运行时根据 assistants.json 的 engine 字段创建引擎实例。

替代 voice_assistant.py 原有的模块级 if/elif/else 硬编码导入，
让 engine 切换不需要改代码。

支持的 engine 值：
  - claude-code  → ClaudeEngine（Claude Code CLI，默认）
  - hermes       → HermesBridge（需 hermes_bridge 模块，不可用时回退 Claude Code）
  - openclaw     → OpenClawBridge（需 openclaw_bridge_websocket 模块，不可用时回退 Claude Code）
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))
_ASSISTANTS_CFG_PATH = os.path.join(_PROJECT_DIR, "config", "assistants.json")


def _read_engine_config() -> str:
    """读取 assistants.json 的 engine 字段。默认 "claude-code"。"""
    try:
        with open(_ASSISTANTS_CFG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return (cfg.get("engine") or "claude-code").strip().lower()
    except Exception:
        return "claude-code"


def get_engine_type() -> str:
    """返回当前配置的 engine 类型字符串。"""
    return _read_engine_config()


def create_engine(agent_id: str = "", namespace: str = ""):
    """根据 assistants.json 创建引擎实例。

    返回 (engine_instance, label_string) 元组。

    引擎实例保证实现 send_and_wait_stream 接口，
    可选方法通过 hasattr 检测（set_history_reader, send_clear_command 等）。
    """
    engine_type = _read_engine_config()

    if engine_type == "claude-code":
        from claude_engine import get_bridge  # noqa: E402
        return get_bridge(agent_id=agent_id, namespace=namespace), "Claude Code"

    elif engine_type == "hermes":
        try:
            from hermes_bridge import get_bridge  # noqa: E402
            return (
                get_bridge(agent_id=agent_id, namespace=namespace),
                "Hermes",
            )
        except ImportError:
            logger.warning(
                "engine=hermes 但 hermes_bridge 模块不可用，回退 Claude Code"
            )
            from claude_engine import get_bridge  # noqa: E402
            return (
                get_bridge(agent_id=agent_id, namespace=namespace),
                "Claude Code (回退)",
            )

    elif engine_type == "openclaw":
        try:
            from openclaw_bridge_websocket import get_bridge  # noqa: E402
            return (
                get_bridge(agent_id=agent_id, namespace=namespace),
                "OpenClaw",
            )
        except ImportError:
            logger.warning(
                "engine=openclaw 但 openclaw_bridge_websocket 模块不可用，回退 Claude Code"
            )
            from claude_engine import get_bridge  # noqa: E402
            return (
                get_bridge(agent_id=agent_id, namespace=namespace),
                "Claude Code (回退)",
            )

    else:
        logger.warning(
            f"未知 engine='{engine_type}'，回退 Claude Code"
        )
        from claude_engine import get_bridge  # noqa: E402
        return (
            get_bridge(agent_id=agent_id, namespace=namespace),
            f"Claude Code (未知引擎 {engine_type})",
        )
