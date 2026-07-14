"""
macOS WeChat Adapter — 微信自动化
翻译自 AppDelegate 中的微信发送逻辑，通过 AppleScript + Accessibility 控制微信
"""

from __future__ import annotations

import subprocess
import time
import logging

logger = logging.getLogger(__name__)


class MacOSWeChatAdapter:
    """macOS 微信适配器"""

    def send_message(self, contact: str, message: str) -> bool:
        """
        自动发送微信消息。

        流程：
        1. 激活微信
        2. Cmd+F 搜索联系人
        3. 输入联系人名
        4. 回车进入对话
        5. 粘贴消息内容
        6. 回车发送
        """
        try:
            self._activate_wechat()
            time.sleep(0.5)

            self._search_contact(contact)
            time.sleep(0.6)

            self._type_message(message)
            time.sleep(0.2)

            self._send()
            logger.info(f"✅ 微信已发送 → {contact}")
            return True

        except Exception as e:
            logger.error(f"微信发送失败: {e}")
            return False

    def _activate_wechat(self):
        subprocess.run(["open", "-a", "WeChat"], capture_output=True, timeout=5)

    def _search_contact(self, contact: str):
        # Cmd+F 打开搜索
        subprocess.run([
            "osascript", "-e",
            'tell application "System Events" to keystroke "f" using {command down}'
        ], capture_output=True, timeout=3)
        time.sleep(0.3)

        # 输入联系人名字
        subprocess.run([
            "osascript", "-e",
            f'tell application "System Events" to keystroke "{contact}"'
        ], capture_output=True, timeout=3)
        time.sleep(0.5)

        # 回车
        subprocess.run([
            "osascript", "-e",
            'tell application "System Events" to keystroke return'
        ], capture_output=True, timeout=3)

    def _type_message(self, message: str):
        # 写入剪贴板
        subprocess.run(["osascript", "-e", f'set the clipboard to "{message}"'],
                       capture_output=True, timeout=3)
        # Cmd+V 粘贴
        subprocess.run([
            "osascript", "-e",
            'tell application "System Events" to keystroke "v" using {command down}'
        ], capture_output=True, timeout=3)

    def _send(self):
        # 回车发送
        subprocess.run([
            "osascript", "-e",
            'tell application "System Events" to keystroke return'
        ], capture_output=True, timeout=3)
