"""Shared fixtures for narractive test suite."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_output(tmp_path):
    """Create a temporary output directory structure."""
    (tmp_path / "narration").mkdir()
    (tmp_path / "diagrams").mkdir()
    (tmp_path / "final").mkdir()
    (tmp_path / "captures").mkdir()
    return tmp_path


@pytest.fixture
def narrator_config(tmp_output):
    """Minimal narrator config pointing at temp dirs."""
    return {
        "engine": "edge-tts",
        "voice": "fr-FR-HenriNeural",
        "output_dir": str(tmp_output / "narration"),
        "speed": "+0%",
    }


@pytest.fixture
def obs_config():
    """Minimal OBS controller config."""
    return {
        "host": "localhost",
        "port": 4455,
        "password": "testpass",
        "scenes": {
            "main": "Main",
            "intro_scene": "Intro",
            "outro_scene": "Outro",
            "diagram_overlay": "Diagram Overlay",
        },
    }


@pytest.fixture
def capture_config(tmp_output):
    """Minimal frame capturer config."""
    return {
        "fps": 10,
        "output_dir": str(tmp_output / "captures"),
        "resolution": "1920x1080",
        "display": ":99",
        "quality": 23,
        "codec": "libx264",
        "format": "mp4",
        "method": "xdotool",
        "scenes": {"main": "Main"},
    }


@pytest.fixture
def assembler_config(tmp_output):
    """Minimal video assembler config."""
    return {
        "final_dir": str(tmp_output / "final"),
        "resolution": "1920x1080",
        "fps": 30,
        "codec": "libx264",
        "quality": 23,
    }


@pytest.fixture
def diagram_config(tmp_output):
    """Minimal diagram generator config."""
    return {
        "output_dir": str(tmp_output / "diagrams"),
        "width": 1920,
        "height": 1080,
        "theme": "dark",
        "background_color": "#1a1a2e",
        "font_family": "Segoe UI",
        "subtitle": "Test Sub",
        "footer_url": "https://example.com",
    }


@pytest.fixture
def fake_recorder():
    """A MagicMock that satisfies the Recorder protocol."""
    recorder = MagicMock()
    recorder.switch_scene = MagicMock()
    recorder.start_recording = MagicMock()
    recorder.stop_recording = MagicMock(return_value="/tmp/recording.mp4")
    recorder.show_diagram_overlay = MagicMock()
    recorder.get_current_scene = MagicMock(return_value="Main")
    recorder.__enter__ = MagicMock(return_value=recorder)
    recorder.__exit__ = MagicMock(return_value=False)
    return recorder


@pytest.fixture
def fake_app():
    """A MagicMock AppAutomator."""
    app = MagicMock()
    app.focus_app = MagicMock()
    app.focus_panel = MagicMock()
    app.wait = MagicMock()
    return app


@pytest.fixture
def full_config(tmp_output):
    """A comprehensive config dict for integration-style tests."""
    return {
        "obs": {
            "host": "localhost",
            "port": 4455,
            "password": "",
            "scenes": {"main": "Main"},
            "output_dir": str(tmp_output / "recordings"),
        },
        "capture": {
            "fps": 10,
            "output_dir": str(tmp_output / "captures"),
            "display": ":99",
        },
        "narration": {
            "engine": "edge-tts",
            "voice": "fr-FR-HenriNeural",
            "output_dir": str(tmp_output / "narration"),
        },
        "diagrams": {
            "output_dir": str(tmp_output / "diagrams"),
        },
        "output": {
            "final_dir": str(tmp_output / "final"),
            "resolution": "1920x1080",
            "fps": 30,
        },
        "subtitles": {
            "enabled": True,
            "max_chars_per_line": 42,
            "max_lines": 2,
            "output_dir": str(tmp_output / "subtitles"),
        },
        "timing": {
            "transition_pause": 0.0,
            "click_delay": 0.0,
            "mouse_move_duration": 0.0,
        },
        "app": {
            "window_title": "Test App",
            "regions": {},
        },
    }


@pytest.fixture
def pronunciation_config():
    """Sample pronunciation config for TextPreprocessor tests."""
    return {
        "acronyms": {
            "QGIS": {"fr": "Q. GIS", "en": "Q. GIS"},
            "FTTH": {"fr": "effe-te-te-ache", "en": "ef-tee-tee-aitch"},
        },
        "spelled": {
            "PDF": {"fr": "pe-de-effe", "en": "pee-dee-ef"},
            "CSV": {"fr": "ce-esse-ve", "en": "see-ess-vee"},
        },
        "proper_nouns": {
            "FilterMate": {"fr": "filtre-mette", "en": "~"},
            "GeoPackage": {"fr": "geo-packaje", "en": "~"},
        },
    }
