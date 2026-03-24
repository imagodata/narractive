"""Tests for config_schema.py — Pydantic v2 validation of config.yaml."""
from __future__ import annotations

import pytest

from narractive.config_schema import is_pydantic_available, validate_config

PYDANTIC_AVAILABLE = is_pydantic_available()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_VALID_CONFIG = {
    "narration": {"engine": "edge-tts"},
}

FULL_VALID_CONFIG = {
    "obs": {
        "host": "localhost",
        "port": 4455,
        "password": "",
        "output_dir": "~/Videos/Test",
        "recording_format": "mkv",
    },
    "app": {
        "window_title": "My App",
        "startup_wait": 5,
        "regions": {},
    },
    "timing": {
        "click_delay": 0.3,
        "type_delay": 0.05,
        "action_pause": 1.0,
        "transition_pause": 2.0,
    },
    "narration": {
        "engine": "edge-tts",
        "voice": "fr-FR-HenriNeural",
        "output_dir": "output/narration",
        "speed": "+0%",
    },
    "languages": {
        "fr": {"voice": "fr-FR-HenriNeural"},
        "en": {"voice": "en-US-GuyNeural"},
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidateConfig:
    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="pydantic not installed")
    def test_empty_dict_returns_config_object(self):
        """An empty dict is valid — all fields have defaults."""
        result = validate_config({})
        assert result is not None

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="pydantic not installed")
    def test_minimal_valid_config_no_exit(self):
        """A minimal valid config should not raise SystemExit."""
        result = validate_config(MINIMAL_VALID_CONFIG)
        assert result is not None

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="pydantic not installed")
    def test_full_valid_config_no_exit(self):
        """A complete valid config should return a NarractiveConfig object."""
        result = validate_config(FULL_VALID_CONFIG)
        assert result is not None
        assert result.narration.engine == "edge-tts"

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="pydantic not installed")
    def test_valid_narration_engines_accepted(self):
        """Known narration engine values should be accepted."""
        for engine in ("edge-tts", "elevenlabs", "kokoro", "f5-tts", "xtts-v2"):
            result = validate_config({"narration": {"engine": engine}})
            assert result is not None

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="pydantic not installed")
    def test_extra_fields_allowed(self):
        """Unknown keys should not cause validation errors."""
        cfg = {
            "narration": {"engine": "edge-tts", "unknown_future_key": True},
            "custom_section": {"foo": "bar"},
        }
        # Should not raise
        result = validate_config(cfg)
        assert result is not None

    @pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="pydantic not installed")
    def test_languages_dict_accessible(self):
        """languages field should be accessible on returned object."""
        result = validate_config(FULL_VALID_CONFIG)
        assert result.languages is not None
        assert "fr" in result.languages

    def test_pydantic_available_flag_is_bool(self):
        assert isinstance(is_pydantic_available(), bool)

    def test_without_pydantic_returns_raw(self):
        """When pydantic is unavailable, validate_config returns the raw dict."""
        if PYDANTIC_AVAILABLE:
            pytest.skip("pydantic is installed")
        result = validate_config(MINIMAL_VALID_CONFIG)
        assert result == MINIMAL_VALID_CONFIG


class TestValidateConfigAndWarn:
    def test_validate_config_and_warn_importable(self):
        """validate_config_and_warn should be importable from config_schema."""
        from narractive.config_schema import validate_config_and_warn

        assert callable(validate_config_and_warn)

    def test_validate_config_and_warn_valid_config_no_exit(self):
        """validate_config_and_warn with a valid config should not raise SystemExit."""
        from narractive.config_schema import validate_config_and_warn

        # Should not raise
        validate_config_and_warn(FULL_VALID_CONFIG)

    def test_validate_config_and_warn_none_config(self):
        """validate_config_and_warn with None should either warn or exit."""
        from narractive.config_schema import validate_config_and_warn

        if not PYDANTIC_AVAILABLE:
            # No pydantic — just warn, no exit
            validate_config_and_warn(None)
        else:
            # With pydantic — None is invalid → SystemExit
            with pytest.raises(SystemExit):
                validate_config_and_warn(None)
