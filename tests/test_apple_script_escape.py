"""
测试 AppleScript 字符串转义 — 防止注入漏洞回归。

三个 adapter（wechat/calendar/reminders）的用户输入必须转义后
才能拼接进 osascript 脚本。任何重构都不能去掉 _esc。
"""
import pytest

from adapters.macos.wechat import _esc as esc_wechat
from adapters.macos.calendar import _esc as esc_calendar
from adapters.macos.reminders import _esc as esc_reminders


class TestEscaping:
    def test_escapes_double_quote(self):
        """双引号必须转义为 \\" """
        assert esc_wechat('a"b') == 'a\\"b'

    def test_escapes_backslash(self):
        """反斜杠必须转义"""
        assert esc_wechat("a\\b") == "a\\\\b"

    def test_escapes_injection_pattern(self):
        """典型注入载荷：引号逃逸 + 注入语句"""
        evil = 'x"; do shell script "rm -rf ~"; --"'
        escaped = esc_wechat(evil)
        assert '"' not in escaped.replace('\\"', "")  # 没有未转义的引号
        assert "\\\"" in escaped

    def test_normal_text_unchanged(self):
        """普通文本不应被改动"""
        assert esc_wechat("你好，先生") == "你好，先生"
        assert esc_wechat("Hello world") == "Hello world"

    def test_newline_survives(self):
        """换行等普通字符不应破坏"""
        assert esc_wechat("line1\nline2") == "line1\nline2"

    def test_all_adapters_escape_consistently(self):
        """三个 adapter 的转义规则必须一致"""
        for evil in ('x"', "a\\b", '"; --"', "正常文本"):
            assert esc_wechat(evil) == esc_calendar(evil)
            assert esc_wechat(evil) == esc_reminders(evil)

    def test_double_escaping_does_not_corrupt(self):
        """重复转义不应把正常文本搞坏（幂等性检查的宽松版）"""
        once = esc_wechat('a"b')
        # 转义一次后再转义，仍应保持合法 AppleScript 字符串
        twice = esc_wechat(once)
        assert '"' not in twice.replace('\\"', "")
