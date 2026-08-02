"""
测试 TTS 分批合成逻辑 — _batch_sentences 按句末标点切分。
"""
import pytest

from speech.tts import _batch_sentences, _env_int


class TestBatchSentences:
    def test_single_sentence_no_split(self):
        text = "你好先生"
        batches = _batch_sentences(text, 4)
        assert len(batches) == 1
        assert batches[0] == "你好先生"

    def test_four_sentences_one_batch(self):
        text = "一。二。三。四。"
        batches = _batch_sentences(text, 4)
        assert len(batches) == 1
        assert batches[0] == "一。二。三。四。"

    def test_five_sentences_split(self):
        text = "一。二。三。四。五。"
        batches = _batch_sentences(text, 4)
        assert len(batches) == 2
        assert batches[0] == "一。二。三。四。"
        assert batches[1] == "五。"

    def test_english_punctuation(self):
        text = "Hello. World! This is a test? Last."
        batches = _batch_sentences(text, 4)
        assert len(batches) == 1

    def test_batch_size_one(self):
        text = "一。二。三。"
        batches = _batch_sentences(text, 1)
        assert len(batches) == 3

    def test_max_sentences_floor_at_one(self):
        """VOICE_ASSISTANT_TTS_MAX_SENTENCES 不能低于 1"""
        import os
        os.environ["VOICE_ASSISTANT_TTS_MAX_SENTENCES"] = "0"
        try:
            batches = _batch_sentences("一。二。", 4)
            assert len(batches) >= 1
        finally:
            os.environ.pop("VOICE_ASSISTANT_TTS_MAX_SENTENCES", None)

    def test_trailing_text_without_punct(self):
        text = "一。二。三。四。最后没有标点的尾巴"
        batches = _batch_sentences(text, 4)
        assert len(batches) == 2
        assert batches[1] == "最后没有标点的尾巴"

    def test_empty_text(self):
        assert _batch_sentences("", 4) == []

    def test_only_punctuation(self):
        # 纯标点：不足 max_sentences 时作为尾部整体返回（strip 非空）
        assert _batch_sentences("。。。", 4) == ["。。。"]


class TestEnvInt:
    def test_default(self):
        assert _env_int("VOICE_ASSISTANT_NONEXISTENT", 42) == 42

    def test_valid(self, monkeypatch):
        monkeypatch.setenv("TEST_ENV_INT", "7")
        assert _env_int("TEST_ENV_INT", 42) == 7

    def test_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("TEST_ENV_INT", "abc")
        assert _env_int("TEST_ENV_INT", 42) == 42

    def test_empty_falls_back(self, monkeypatch):
        monkeypatch.setenv("TEST_ENV_INT", "")
        assert _env_int("TEST_ENV_INT", 42) == 42
