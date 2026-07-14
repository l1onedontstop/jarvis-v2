"""
macOS Reminders Adapter — 提醒事项集成
翻译自 RemindersBridge.swift，通过 EventKit + osascript 访问提醒事项
"""

from __future__ import annotations

import subprocess
import logging

logger = logging.getLogger(__name__)


class MacOSRemindersAdapter:
    """macOS 提醒事项适配器"""

    def get_uncompleted(self) -> list[dict]:
        """获取所有未完成提醒事项"""
        script = '''
        tell application "Reminders"
            set reminderList to {}
            repeat with lst in lists
                repeat with rem in (reminders in lst whose completed is false)
                    set remInfo to {name of rem}
                    try
                        set remInfo to remInfo & (due date of rem) as string
                    end try
                    set reminderList to reminderList & {remInfo}
                end repeat
            end repeat
            return reminderList
        end tell
        '''
        result = self._run_applescript(script)
        reminders = []
        if result:
            for line in result.split("\n"):
                line = line.strip()
                if line:
                    reminders.append({"title": line})
        return reminders

    def create(self, title: str, due_date: str = "") -> bool:
        """创建新提醒事项"""
        script = f'''
        tell application "Reminders"
            tell list "提醒事項"
                make new reminder with properties {{name:"{title}"}}
            end tell
        end tell
        return true
        '''
        return self._run_applescript_bool(script)

    def complete(self, title: str) -> bool:
        """根据标题完成提醒事项"""
        script = f'''
        tell application "Reminders"
            repeat with lst in lists
                repeat with rem in (reminders in lst whose completed is false)
                    if name of rem contains "{title}" then
                        set completed of rem to true
                    end if
                end repeat
            end repeat
        end tell
        return true
        '''
        return self._run_applescript_bool(script)

    def _run_applescript(self, script: str) -> str:
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Reminders AppleScript 失败: {e}")
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
