import json
from pathlib import Path
from unittest.mock import Mock

from assistants import AssistantInstance
from assistants.jarvis.tts import JarvisTTS, JarvisV2OnnxTTS


PROJECT_DIR = Path(__file__).resolve().parent.parent


def _jarvis_config():
    config = json.loads((PROJECT_DIR / "config" / "assistants.json").read_text())
    return next(item for item in config["assistants"] if item["id"] == "jarvis")


def test_default_jarvis_routes_to_melotts(monkeypatch):
    config = _jarvis_config()
    backend = Mock()
    backend.is_available.return_value = True
    monkeypatch.setattr("assistants.jarvis.tts.JarvisV2OnnxTTS", lambda value: backend)

    instance = AssistantInstance("jarvis", config, hud_enabled=False)

    assert config["components"]["tts"] == "jarvis_v2_onnx_lang_sch"
    assert instance.tts is backend


def test_melotts_adapter_uses_bilingual_backend(monkeypatch):
    from assistants.jarvis import tts_melotts_onnx

    configure = Mock()
    preload = Mock()
    synthesize = Mock(return_value="voice.wav")
    monkeypatch.setattr(tts_melotts_onnx, "configure", configure)
    monkeypatch.setattr(tts_melotts_onnx, "preload", preload)
    monkeypatch.setattr(tts_melotts_onnx, "synthesize", synthesize)

    adapter = JarvisV2OnnxTTS({"sample_rate": 44100})
    result = adapter.synthesize("你好, systems online.")

    configure.assert_called_once_with({"sample_rate": 44100})
    preload.assert_called_once_with()
    synthesize.assert_called_once_with("你好, systems online.", output_path=None)
    assert result == "voice.wav"


def test_legacy_jarvis_adapter_never_routes_to_zipvoice(monkeypatch):
    from assistants.jarvis import tts_piper

    configure = Mock()
    synthesize = Mock(return_value="piper.wav")
    monkeypatch.setattr(tts_piper, "configure", configure)
    monkeypatch.setattr(tts_piper, "synthesize", synthesize)

    adapter = JarvisTTS({"speed": 1.2})
    result = adapter.synthesize("中文也只走显式选择的 Piper")

    configure.assert_called_once_with({"speed": 1.2})
    synthesize.assert_called_once_with("中文也只走显式选择的 Piper", output_path=None)
    assert result == "piper.wav"


def test_model_config_is_44100_hz():
    config = json.loads(
        (PROJECT_DIR / "models" / "jarvis-v2-melotts-onnx-lang-sch" / "config.json").read_text()
    )

    assert config["data"]["sampling_rate"] == 44100
