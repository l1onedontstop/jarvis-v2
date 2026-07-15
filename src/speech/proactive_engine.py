#!/usr/bin/env python3
"""
Proactive Engine — 主动关怀与提醒

从 V1 ProactiveEngine.swift 移植。定期检查系统状态，在合适的时机主动说话。
- 低电量提醒
- 午餐/晚安提醒
- 连续工作超时提醒
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def _get_battery() -> tuple[float, bool] | None:
    """返回 (电量比例 0-1, 是否充电中)，非笔记本返回 None。"""
    try:
        out = subprocess.check_output(
            ["pmset", "-g", "batt"], text=True, timeout=5
        )
    except Exception:
        return None
    m = re.search(r"(\d+)%", out)
    if not m:
        return None
    level = int(m.group(1)) / 100.0
    charging = "charging" in out or "AC Power" in out
    return level, charging


class ProactiveEngine:
    """主动引擎 — 定时检查并在合适时机触发回调。

    用法:
        engine = ProactiveEngine()
        engine.on_speak = lambda msg: voice_assistant.speak(msg)
        engine.start()
    """

    def __init__(self):
        self._running = False
        self._timers: list[threading.Timer] = []
        self._work_start = time.time()
        self._last_battery_warn: float = 0
        self._last_break_reminder: float = 0
        self._last_time_check: str = ""  # 日期，避免同一天重复触发

        # 回调：当引擎决定要说点什么时调用
        self.on_speak = None  # callable(str)
        self.on_camera_check = None  # callable() → 待机摄像头存在检测

    def start(self):
        if self._running:
            return
        self._running = True
        self._work_start = time.time()
        self._schedule_battery()
        self._schedule_time()
        self._schedule_work()
        self._schedule_camera()
        logger.info("🔔 Proactive Engine 已启动")

    def stop(self):
        self._running = False
        for t in self._timers:
            t.cancel()
        self._timers.clear()
        logger.info("🔔 Proactive Engine 已停止")

    def reset_work_timer(self):
        """用户活跃时重置工作计时器。"""
        self._work_start = time.time()

    def touch(self):
        """用户有交互，重置工作计时。"""
        self.reset_work_timer()

    # ── 定时器 ──────────────────────────────────────────────

    def _schedule_battery(self):
        if not self._running:
            return
        self._check_battery()
        t = threading.Timer(120, self._schedule_battery)
        t.daemon = True
        t.start()
        self._timers.append(t)

    def _schedule_time(self):
        if not self._running:
            return
        self._check_time_milestones()
        t = threading.Timer(300, self._schedule_time)
        t.daemon = True
        t.start()
        self._timers.append(t)

    def _schedule_camera(self):
        if not self._running:
            return
        self._check_camera_presence()
        t = threading.Timer(1800, self._schedule_camera)  # 每 30 分钟
        t.daemon = True
        t.start()
        self._timers.append(t)

    def _schedule_work(self):
        if not self._running:
            return
        self._check_work_session()
        t = threading.Timer(600, self._schedule_work)
        t.daemon = True
        t.start()
        self._timers.append(t)

    # ── 检查逻辑 ────────────────────────────────────────────

    def _check_battery(self):
        result = _get_battery()
        if result is None:
            return
        level, charging = result
        since_warn = time.time() - self._last_battery_warn

        if not charging and level < 0.08 and since_warn > 300:
            self._last_battery_warn = time.time()
            self._speak("电量严重不足，请立即充电。")

        elif not charging and level < 0.15 and since_warn > 600:
            self._last_battery_warn = time.time()
            self._speak(f"先生，电量只剩{int(level * 100)}%了，建议插上电源。")

    def _check_time_milestones(self):
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        if today == self._last_time_check:
            return

        hour, minute = now.hour, now.minute
        if hour == 12 and 0 <= minute <= 5:
            self._last_time_check = today
            self._speak("先生，中午了，记得吃午饭。")
        elif hour == 23 and 0 <= minute <= 5:
            self._last_time_check = today
            self._speak("先生，已经晚上11点了，早点休息吧。")

    def _check_work_session(self):
        elapsed = time.time() - self._work_start
        since_reminder = time.time() - self._last_break_reminder
        if elapsed > 7200 and since_reminder > 7200:
            self._last_break_reminder = time.time()
            hrs = int(elapsed / 3600)
            self._speak(f"先生，你已经连续工作{hrs}小时了，建议起来活动一下。")

    def _check_camera_presence(self):
        """待机摄像头存在检测：抓帧 → 检测是否有人。有人则触发回调。"""
        if self.on_camera_check:
            try:
                self.on_camera_check()
            except Exception:
                pass

    def _speak(self, msg: str):
        if self.on_speak:
            try:
                self.on_speak(msg)
            except Exception:
                pass
