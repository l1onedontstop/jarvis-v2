"""
macOS Calendar Adapter — 日历集成
翻译自 CalendarBridge.swift，通过 EventKit + osascript 访问日历
"""

from __future__ import annotations

import subprocess
import json
import logging
from datetime import datetime, timedelta
from ..base import PlatformAdapter

logger = logging.getLogger(__name__)


class MacOSCalendarAdapter:
    """macOS 日历适配器"""

    def get_today_events(self) -> list[dict]:
        """获取今日日历事件"""
        script = '''
        tell application "Calendar"
            set todayStart to (current date) - (time of (current date))
            set todayEnd to todayStart + 24 * hours
            set eventList to {}
            repeat with cal in calendars
                set theEvents to (every event in cal whose start date ≥ todayStart and start date < todayEnd)
                repeat with evt in theEvents
                    set endStr to ""
                    try
                        set endStr to (end date of evt) as string
                    end try
                    set eventList to eventList & {{summary of evt, (start date of evt) as string, endStr}}
                end repeat
            end repeat
            return eventList
        end tell
        '''
        result = self._run_applescript(script)
        events = []
        if result:
            for item in result.split(", "):
                events.append({"summary": item.strip()})
        return events

    def create_event(self, title: str, date_str: str = "", time_str: str = "") -> bool:
        """创建新日历事件。date_str 格式：今天/明天/2026-07-15"""
        # 解析日期
        target_date = self._parse_date(date_str) if date_str else datetime.now()

        script = f'''
        tell application "Calendar"
            set theCal to first calendar
            set startDate to current date
            set startDate's year to {target_date.year}
            set startDate's month to {target_date.month}
            set startDate's day to {target_date.day}
            set startDate's hours to 9
            set startDate's minutes to 0
            set startDate's seconds to 0
            set endDate to startDate + (60 * minutes)
            make new event at theCal with properties {{summary:"{title}", start date:startDate, end date:endDate}}
        end tell
        return true
        '''
        return self._run_applescript_bool(script)

    def _parse_date(self, date_str: str) -> datetime:
        """解析中文日期表达式"""
        now = datetime.now()
        date_str = date_str.strip()
        if date_str in ("今天", "今日", ""):
            return now
        if date_str in ("明天", "明日"):
            return now + timedelta(days=1)
        if date_str == "后天":
            return now + timedelta(days=2)
        # ISO 格式
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return now

    def _run_applescript(self, script: str) -> str:
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip()
        except Exception as e:
            logger.warning(f"AppleScript 失败: {e}")
            return ""

    def _run_applescript_bool(self, script: str) -> bool:
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=10
            )
            return True
        except Exception:
            return False
