"""
测试快路径路由 — needs_live_data / is_obviously_light 的判定逻辑。
"""
import pytest

from speech import routing
from speech.routing import needs_live_data, is_obviously_light, handoff_intent


class TestNeedsLiveData:
    def test_freshness_marker_alone(self):
        """仅有新鲜度标记但无外部域 → 非实时"""
        assert needs_live_data("最新情况如何") is True  # 有"最新情况"模式
        assert needs_live_data("今天的安排") is False

    def test_external_domain_alone(self):
        """仅有外部域但无新鲜度标记 → 非实时"""
        assert needs_live_data("世界杯") is False

    def test_both_marks_live(self):
        """外部域 + 新鲜度标记 → 实时"""
        assert needs_live_data("目前世界杯情况怎么样") is True
        assert needs_live_data("今天股价走势") is True

    def test_empty_input(self):
        assert needs_live_data("") is False
        assert needs_live_data(None) is False

    def test_weather_is_live(self):
        assert needs_live_data("今天天气怎么样") is True

    def test_finance_is_live(self):
        assert needs_live_data("最新金价") is True
        assert needs_live_data("今天汇率走势") is True  # 外部域 + 新鲜度标记

    def test_case_insensitive_english(self):
        assert needs_live_data("what is the latest stock price") is True


class TestIsObviouslyLight:
    def test_greeting_is_light(self):
        assert is_obviously_light("你好") is True

    def test_live_data_not_light(self):
        """实时数据请求必须升级 agent，不能走快路径"""
        assert is_obviously_light("目前世界杯情况怎么样") is False
        assert is_obviously_light("今天天气怎么样") is False

    def test_empty_not_light(self):
        assert is_obviously_light("") is False


class TestHandoffIntent:
    def test_live_data_handoff(self):
        assert handoff_intent("目前世界杯情况怎么样") == "live_data"

    def test_empty(self):
        assert handoff_intent("") == ""
