"""
macOS System Adapter — 系统控制
翻译自 SystemController.swift + HotkeyManager.swift
通过 osascript + open 控制系统功能
"""

from __future__ import annotations

import subprocess
import logging

logger = logging.getLogger(__name__)


class MacOSSystemAdapter:
    """macOS 系统控制适配器"""

    def set_volume(self, level: int) -> bool:
        """设置系统音量 0-100"""
        try:
            subprocess.run(
                ["osascript", "-e", f"set volume output volume {max(0, min(100, level))}"],
                capture_output=True, timeout=5
            )
            return True
        except Exception:
            return False

    def volume_up(self, step: int = 10):
        subprocess.run(["osascript", "-e",
            f"set volume output volume (output volume of (get volume settings) + {step})"],
            capture_output=True, timeout=5)

    def volume_down(self, step: int = 10):
        subprocess.run(["osascript", "-e",
            f"set volume output volume (output volume of (get volume settings) - {step})"],
            capture_output=True, timeout=5)

    def mute(self):
        subprocess.run(["osascript", "-e", "set volume with output muted"],
                       capture_output=True, timeout=5)

    def unmute(self):
        subprocess.run(["osascript", "-e", "set volume without output muted"],
                       capture_output=True, timeout=5)

    def lock_screen(self) -> bool:
        """锁屏"""
        try:
            subprocess.run(
                ["osascript", "-e", 'tell app "System Events" to keystroke "q" using {control down, command down}'],
                capture_output=True, timeout=5
            )
            return True
        except Exception:
            return False

    def sleep(self) -> bool:
        """休眠"""
        try:
            subprocess.run(
                ["osascript", "-e", 'tell app "System Events" to sleep'],
                capture_output=True, timeout=5
            )
            return True
        except Exception:
            return False

    def open_app(self, app_name: str) -> bool:
        """打开应用"""
        try:
            subprocess.run(["open", "-a", app_name], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    def open_url(self, url: str) -> bool:
        """在默认浏览器中打开 URL"""
        try:
            fixed = url if url.startswith("http") else f"https://{url}"
            subprocess.run(["open", fixed], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    def screenshot(self, path: str = "/tmp/jarvis_screenshot.png") -> str:
        """截屏"""
        try:
            subprocess.run(["screencapture", "-i", path], capture_output=True, timeout=30)
            return path
        except Exception:
            return ""

    def get_frontmost_app(self) -> str:
        """获取当前最前应用名称"""
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def dock_autohide(self, enabled: bool = True):
        """自动隐藏 Dock"""
        val = "true" if enabled else "false"
        subprocess.run(
            ["osascript", "-e", f"tell application \"System Events\" to set autohide of dock preferences to {val}"],
            capture_output=True, timeout=5
        )
