"""
Platform Adapter 抽象接口

所有平台适配器必须实现此接口。
macOS 和 Windows 各提供一套实现。
"""

from __future__ import annotations
from abc import ABC, abstractmethod


class PlatformAdapter(ABC):
    """平台适配器基类"""

    @abstractmethod
    def send_wechat(self, contact: str, message: str) -> bool:
        """发送微信消息"""
        ...

    @abstractmethod
    def get_calendar_events(self, date: str = "") -> list[dict]:
        """获取日历事件"""
        ...

    @abstractmethod
    def create_reminder(self, title: str, due_date: str = "") -> bool:
        """创建提醒事项"""
        ...

    @abstractmethod
    def get_reminders(self) -> list[dict]:
        """获取未完成提醒"""
        ...

    @abstractmethod
    def open_app(self, app_name: str) -> bool:
        """打开应用"""
        ...

    @abstractmethod
    def set_volume(self, level: int) -> bool:
        """设置系统音量 (0-100)"""
        ...

    @abstractmethod
    def lock_screen(self) -> bool:
        """锁屏"""
        ...

    @abstractmethod
    def sleep(self) -> bool:
        """休眠"""
        ...

    @abstractmethod
    def screenshot(self, path: str = "") -> str:
        """截屏，返回文件路径"""
        ...

    @abstractmethod
    def get_frontmost_app(self) -> str:
        """获取最前应用名称"""
        ...
