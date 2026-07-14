"""
QuickActions — 本地规则匹配，零延迟响应

从 Swift QuickActions.swift 翻译而来。
规则匹配后返回 (action_type, params) 或 None。
Markers 系统：识别 [STEP_ASIDE]、[FOCUS_MODE] 等控制标记。
"""

from __future__ import annotations

import re
import json
import logging
import platform
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# 平台适配器（延迟加载）
_system_adapter = None
_wechat_adapter = None
_calendar_adapter = None
_reminders_adapter = None


def _get_system():
    global _system_adapter
    if _system_adapter is None and platform.system() == "Darwin":
        from adapters.macos.system import MacOSSystemAdapter
        _system_adapter = MacOSSystemAdapter()
    return _system_adapter


def _get_wechat():
    global _wechat_adapter
    if _wechat_adapter is None and platform.system() == "Darwin":
        from adapters.macos.wechat import MacOSWeChatAdapter
        _wechat_adapter = MacOSWeChatAdapter()
    return _wechat_adapter


def _get_calendar():
    global _calendar_adapter
    if _calendar_adapter is None and platform.system() == "Darwin":
        from adapters.macos.calendar import MacOSCalendarAdapter
        _calendar_adapter = MacOSCalendarAdapter()
    return _calendar_adapter


def _get_reminders():
    global _reminders_adapter
    if _reminders_adapter is None and platform.system() == "Darwin":
        from adapters.macos.reminders import MacOSRemindersAdapter
        _reminders_adapter = MacOSRemindersAdapter()
    return _reminders_adapter

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "quick_actions.json"


# ── 默认规则（内置）──────────────────────────────────────

_DEFAULT_RULES = [
    # ── 时间/日期 ──
    {"pattern": r"(几点|几号|日期|星期几|什么日子)", "action": "time_date", "priority": 100},
    # ── 待机 ──
    {"pattern": r"(退下|休息|不打扰|你先退下|下去吧|待机)", "action": "standby", "priority": 100},
    # ── 音量 ──
    {"pattern": r"(音量大|大声|音量小|小声|静音|取消静音)", "action": "volume", "priority": 90},
    # ── 锁屏/休眠 ──
    {"pattern": r"(锁屏|锁定屏幕|休眠|sleep|睡觉)", "action": "system_sleep", "priority": 90},
    # ── 打开应用 ──
    {"pattern": r"打开\s*(.+)", "action": "open_app", "priority": 80},
    # ── 搜索 ──
    {"pattern": r"(搜索|查一下|帮我查|搜一下)\s*(.+)", "action": "search_web", "priority": 80},
    # ── 截屏 ──
    {"pattern": r"(截屏|截图|screenshot)", "action": "screenshot", "priority": 80},
    # ── 问候 ──
    {"pattern": r"^(你好|哈喽|hi|hello|嘿|早上好|下午好|晚上好)$", "action": "greeting", "priority": 50},
    # ── 感谢 ──
    {"pattern": r"^(谢谢|多谢|thank|thanks|3Q)$", "action": "thanks", "priority": 50},
]


class QuickActions:
    """本地快速动作匹配引擎"""

    def __init__(self):
        self._rules: list[dict] = []
        self._load_rules()
        self.on_step_aside = None       # callable(mode)
        self.on_send_wechat = None      # callable(contact, message)
        self.on_focus_mode = None       # callable(enter: bool)
        self._missed_queries: list[str] = []

    def _load_rules(self):
        """加载规则：优先从 JSON 配置，回退到内置默认"""
        if _CONFIG_PATH.exists():
            try:
                with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._rules = data.get("rules", [])
                logger.info(f"从配置文件加载 {len(self._rules)} 条 QuickAction 规则")
                return
            except Exception as e:
                logger.warning(f"加载 QuickActions 配置失败: {e}")
        self._rules = _DEFAULT_RULES
        logger.info(f"使用内置 {len(self._rules)} 条默认 QuickAction 规则")

    def match(self, text: str) -> dict | None:
        """
        匹配用户输入，返回 action dict 或 None。
        action dict 格式：{"action": "time_date", "params": {...}, "marker": "..."}
        """
        text = text.strip()
        if not text:
            return None

        # 1) 先检查 Markers
        marker_result = self._check_markers(text)
        if marker_result:
            return marker_result

        # 2) 按优先级匹配规则
        rules = sorted(self._rules, key=lambda r: r.get("priority", 0), reverse=True)
        for rule in rules:
            pattern = rule.get("pattern", "")
            try:
                m = re.search(pattern, text, re.IGNORECASE)
            except re.error:
                continue
            if m:
                action_type = rule["action"]
                params = {}
                if m.groups():
                    # 提取命名组或位置组
                    named = {k: v for k, v in m.groupdict().items() if v}
                    if named:
                        params = named
                    else:
                        params = {"value": m.group(1) if m.lastindex else m.group()}
                return {"action": action_type, "params": params}

        # 3) 未命中，记录以便后续分析
        self._missed_queries.append(text)
        return None

    def _check_markers(self, text: str) -> dict | None:
        """检查文本中的 Markers 标记"""
        # [STEP_ASIDE:mode]
        m = re.search(r"\[STEP_ASIDE:(\w+)\]", text)
        if m:
            return {"action": "marker_step_aside", "params": {"mode": m.group(1)}}

        # [FOCUS_MODE:enter/exit]
        m = re.search(r"\[FOCUS_MODE:(enter|exit)\]", text)
        if m:
            return {"action": "marker_focus_mode", "params": {"enter": m.group(1) == "enter"}}

        # [SEND_WECHAT:contact:message]
        m = re.search(r"\[SEND_WECHAT:([^:]+):(.+)\]", text)
        if m:
            return {"action": "marker_send_wechat", "params": {"contact": m.group(1), "message": m.group(2)}}

        # 微信快捷指令
        m = re.search(r"给\s*(.+)\s*发微信说\s*(.+)", text)
        if m:
            return {"action": "send_wechat", "params": {"contact": m.group(1).strip(), "message": m.group(2).strip()}}

        return None

    def get_missed(self) -> list[str]:
        """获取所有未命中的查询（用于分析扩展规则）"""
        return list(self._missed_queries)

    def clear_missed(self):
        self._missed_queries.clear()


# ── Action Executor ───────────────────────────────────────

class ActionExecutor:
    """执行 QuickAction 匹配到的动作"""

    def __init__(self):
        self.quick_actions = QuickActions()

    def execute(self, action: dict) -> str | None:
        """
        执行动作，返回需要 TTS 播报的文本（None 表示不需要播报）。
        """
        action_type = action.get("action", "")
        params = action.get("params", {})

        handlers = {
            "time_date": self._handle_time_date,
            "standby": self._handle_standby,
            "volume": self._handle_volume,
            "system_sleep": self._handle_sleep,
            "open_app": self._handle_open_app,
            "search_web": self._handle_search,
            "screenshot": self._handle_screenshot,
            "greeting": self._handle_greeting,
            "thanks": self._handle_thanks,
            "send_wechat": self._handle_send_wechat,
            "marker_step_aside": self._handle_marker_step_aside,
            "marker_focus_mode": self._handle_marker_focus_mode,
            "marker_send_wechat": self._handle_marker_send_wechat,
        }

        handler = handlers.get(action_type)
        if handler:
            return handler(params)
        return None

    # ── 具体处理器 ──

    def _handle_time_date(self, params: dict) -> str:
        now = datetime.now()
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        wd = weekdays[now.weekday()]
        return f"现在是{now.year}年{now.month}月{now.day}日，{wd}，{now.hour}点{now.minute}分。"

    def _handle_standby(self, params: dict) -> str:
        if self.quick_actions.on_step_aside:
            self.quick_actions.on_step_aside("rest")
        return "好的，我退下了。需要时请叫我。"

    def _handle_volume(self, params: dict) -> str:
        sys_adapter = _get_system()
        text = params.get("value", "")
        if not sys_adapter:
            return "音量控制仅支持 macOS"
        if "大" in text or "大声" in text:
            sys_adapter.volume_up()
            return "音量已调大"
        elif "小" in text:
            sys_adapter.volume_down()
            return "音量已调小"
        elif "静音" in text:
            sys_adapter.mute()
            return "已静音"
        return "音量已调整"

    def _handle_sleep(self, params: dict) -> str:
        sys_adapter = _get_system()
        if sys_adapter:
            sys_adapter.sleep()
        return ""

    def _handle_open_app(self, params: dict) -> str:
        name = params.get("value", "").strip()
        if not name:
            return "你想打开什么？"
        sys_adapter = _get_system()
        if sys_adapter:
            ok = sys_adapter.open_app(name)
            return f"已打开{name}" if ok else f"抱歉，无法打开{name}"
        return f"已尝试打开{name}"

    def _handle_search(self, params: dict) -> str:
        return ""  # 交回主流程，由 Claude 处理搜索

    def _handle_screenshot(self, params: dict) -> str:
        sys_adapter = _get_system()
        if sys_adapter:
            path = sys_adapter.screenshot()
            return f"截图已保存" if path else "截图失败"
        return "截图功能仅支持 macOS"

    def _handle_greeting(self, params: dict) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "早上好先生，有什么我可以效劳的？"
        elif hour < 18:
            return "下午好先生，随时为您效劳。"
        else:
            return "晚上好先生，今天辛苦了。"

    def _handle_thanks(self, params: dict) -> str:
        return "不客气，随时为您效劳。"

    def _handle_send_wechat(self, params: dict) -> str:
        wechat = _get_wechat()
        if wechat:
            wechat.send_message(params["contact"], params["message"])
        elif self.quick_actions.on_send_wechat:
            self.quick_actions.on_send_wechat(params["contact"], params["message"])
        return f"正在给{params['contact']}发送微信"

    def _handle_marker_step_aside(self, params: dict) -> str:
        if self.quick_actions.on_step_aside:
            self.quick_actions.on_step_aside(params.get("mode", "rest"))
        return ""

    def _handle_marker_focus_mode(self, params: dict) -> str:
        if self.quick_actions.on_focus_mode:
            self.quick_actions.on_focus_mode(params["enter"])
        return ""

    def _handle_marker_send_wechat(self, params: dict) -> str:
        if self.quick_actions.on_send_wechat:
            self.quick_actions.on_send_wechat(params["contact"], params["message"])
        return ""


# 全局
_quick_actions: QuickActions | None = None
_action_executor: ActionExecutor | None = None


def get_quick_actions() -> QuickActions:
    global _quick_actions
    if _quick_actions is None:
        _quick_actions = QuickActions()
    return _quick_actions


def get_action_executor() -> ActionExecutor:
    global _action_executor
    if _action_executor is None:
        _action_executor = ActionExecutor()
    return _action_executor
