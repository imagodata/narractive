"""Tests for OBSController (config, scenes, compatibility methods)."""
from __future__ import annotations

import pytest

from video_automation.core.obs_controller import OBSController


class TestOBSController:
    def test_init_defaults(self):
        obs = OBSController({})
        assert obs.host == "localhost"
        assert obs.port == 4455
        assert obs.password == ""
        assert obs.scenes == {}

    def test_init_custom_config(self):
        obs = OBSController({
            "host": "192.168.1.10",
            "port": 5555,
            "password": "secret",
            "scenes": {"main": "Main", "intro_scene": "Intro"},
        })
        assert obs.host == "192.168.1.10"
        assert obs.port == 5555
        assert obs.scenes["main"] == "Main"

    def test_require_client_raises_when_not_connected(self):
        obs = OBSController({})
        with pytest.raises(RuntimeError, match="Not connected"):
            obs._require_client()

    def test_transition_to_qgis_alias_exists(self):
        """Backward compat: transition_to_qgis is an alias."""
        assert OBSController.transition_to_qgis is OBSController.transition_to_main
