"""Tests for the package-level imports and version."""
from __future__ import annotations

import pytest


class TestPackageInit:
    def test_version_is_string(self):
        from narractive import __version__
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_backward_compat_qgis_automator_import(self):
        """The shim module should still expose QGISAutomator."""
        pytest.importorskip("pyautogui")
        from narractive.core.qgis_automator import QGISAutomator
        from narractive.core.app_automator import AppAutomator
        assert QGISAutomator is AppAutomator

    def test_recorder_protocol_importable(self):
        from narractive.sequences.base import Recorder
        assert hasattr(Recorder, "connect")
        assert hasattr(Recorder, "start_recording")
