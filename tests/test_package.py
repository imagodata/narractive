"""Tests for the package-level imports and version."""

from __future__ import annotations

import pytest


class TestPackageInit:
    def test_version_is_string(self):
        from video_automation import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_backward_compat_qgis_automator_import(self):
        """The shim module should still expose QGISAutomator."""
        try:
            pytest.importorskip("pyautogui")
        except Exception:
            pytest.skip("pyautogui unavailable (no display)")
        from video_automation.core.app_automator import AppAutomator
        from video_automation.core.qgis_automator import QGISAutomator

        assert QGISAutomator is AppAutomator

    def test_recorder_protocol_importable(self):
        from video_automation.sequences.base import Recorder

        assert hasattr(Recorder, "connect")
        assert hasattr(Recorder, "start_recording")
