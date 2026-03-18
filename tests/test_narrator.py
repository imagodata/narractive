"""Tests for the Narrator class (TTS engine selection, config parsing)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_automation.core.narrator import Narrator


@pytest.fixture
def narrator_config(tmp_path):
    return {
        "engine": "edge-tts",
        "voice": "fr-FR-HenriNeural",
        "output_dir": str(tmp_path / "narration"),
        "speed": "+0%",
    }


class TestNarrator:
    def test_init_defaults(self, tmp_path):
        n = Narrator({"output_dir": str(tmp_path / "out")})
        assert n.engine == "edge-tts"
        assert n.voice == "fr-FR-HenriNeural"
        assert n.speed == "+0%"

    def test_init_custom_engine(self, tmp_path):
        n = Narrator({"engine": "elevenlabs", "voice": "test_voice", "output_dir": str(tmp_path)})
        assert n.engine == "elevenlabs"
        assert n.voice == "test_voice"

    def test_init_creates_output_dir(self, narrator_config, tmp_path):
        n = Narrator(narrator_config)
        assert (tmp_path / "narration").is_dir()

    def test_unknown_engine_raises(self, narrator_config):
        narrator_config["engine"] = "nonexistent"
        n = Narrator(narrator_config)
        with pytest.raises(ValueError, match="Unknown TTS engine"):
            n.generate_narration("Hello", "test.mp3")

    def test_f5_config(self, tmp_path):
        n = Narrator({
            "engine": "f5-tts",
            "output_dir": str(tmp_path),
            "f5_ref_audio": "ref.wav",
            "f5_ref_text": "reference",
            "f5_model": "CustomModel",
            "f5_speed": 1.2,
            "f5_conda_env": "my-env",
            "f5_remove_silence": True,
        })
        assert n.f5_ref_audio == "ref.wav"
        assert n.f5_model == "CustomModel"
        assert n.f5_speed == 1.2
        assert n.f5_remove_silence is True

    def test_generate_all_narrations_empty(self, narrator_config):
        n = Narrator(narrator_config)
        results = n.generate_all_narrations({})
        assert results == {}
