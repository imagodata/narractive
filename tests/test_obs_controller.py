"""Tests for OBSController — config, connection, scenes, recording, screenshots."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from video_automation.core.obs_controller import OBSController


# ---------------------------------------------------------------------------
# Init and config
# ---------------------------------------------------------------------------


class TestOBSControllerInit:
    def test_defaults(self):
        obs = OBSController({})
        assert obs.host == "localhost"
        assert obs.port == 4455
        assert obs.password == ""
        assert obs.scenes == {}

    def test_custom_config(self):
        obs = OBSController({
            "host": "192.168.1.10",
            "port": 5555,
            "password": "secret",
            "scenes": {"main": "Main", "intro_scene": "Intro"},
        })
        assert obs.host == "192.168.1.10"
        assert obs.port == 5555
        assert obs.password == "secret"
        assert obs.scenes["main"] == "Main"

    def test_client_initially_none(self):
        obs = OBSController({})
        assert obs._client is None


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


class TestOBSControllerConnection:
    def test_require_client_raises_when_not_connected(self):
        obs = OBSController({})
        with pytest.raises(RuntimeError, match="Not connected"):
            obs._require_client()

    def test_disconnect_when_not_connected(self):
        obs = OBSController({})
        # Should not raise
        obs.disconnect()
        assert obs._client is None

    def test_disconnect_calls_client_disconnect(self):
        obs = OBSController({})
        obs._client = MagicMock()
        obs.disconnect()
        assert obs._client is None

    @patch("video_automation.core.obs_controller.time.sleep")
    def test_connect_import_error(self, mock_sleep):
        obs = OBSController({})
        with patch.dict("sys.modules", {"obsws_python": None}):
            with pytest.raises(ImportError):
                obs.connect()

    def test_context_manager_calls_connect_disconnect(self):
        obs = OBSController({})
        obs.connect = MagicMock()
        obs.disconnect = MagicMock()
        with obs:
            obs.connect.assert_called_once()
        obs.disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# Scene management (requires mock client)
# ---------------------------------------------------------------------------


class TestOBSSceneManagement:
    def setup_method(self):
        self.obs = OBSController({"scenes": {
            "main": "Main",
            "intro_scene": "Intro",
            "outro_scene": "Outro",
            "diagram_overlay": "Diagram Overlay",
        }})
        self.obs._client = MagicMock()

    def test_switch_scene(self):
        self.obs.switch_scene("Custom Scene")
        self.obs._client.set_current_program_scene.assert_called_once_with("Custom Scene")

    def test_switch_scene_failure_raises(self):
        self.obs._client.set_current_program_scene.side_effect = RuntimeError("fail")
        with pytest.raises(RuntimeError):
            self.obs.switch_scene("Bad")

    def test_get_current_scene(self):
        resp = MagicMock()
        resp.scene_name = "Main"
        self.obs._client.get_current_program_scene.return_value = resp
        assert self.obs.get_current_scene() == "Main"

    def test_list_scenes(self):
        resp = MagicMock()
        resp.scenes = [{"sceneName": "A"}, {"sceneName": "B"}]
        self.obs._client.get_scene_list.return_value = resp
        assert self.obs.list_scenes() == ["A", "B"]


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


class TestOBSRecording:
    def setup_method(self):
        self.obs = OBSController({})
        self.obs._client = MagicMock()

    def test_start_recording(self):
        self.obs.start_recording()
        self.obs._client.start_record.assert_called_once()

    def test_start_recording_failure_raises(self):
        self.obs._client.start_record.side_effect = RuntimeError("already recording")
        with pytest.raises(RuntimeError):
            self.obs.start_recording()

    def test_stop_recording_returns_path(self):
        resp = MagicMock()
        resp.output_path = "/tmp/video.mkv"
        self.obs._client.stop_record.return_value = resp
        result = self.obs.stop_recording()
        assert result == "/tmp/video.mkv"

    def test_stop_recording_no_path(self):
        resp = MagicMock(spec=[])  # no output_path attribute
        self.obs._client.stop_record.return_value = resp
        result = self.obs.stop_recording()
        assert result is None

    def test_pause_recording(self):
        self.obs.pause_recording()
        self.obs._client.pause_record.assert_called_once()

    def test_resume_recording(self):
        self.obs.resume_recording()
        self.obs._client.resume_record.assert_called_once()

    def test_get_recording_status(self):
        resp = MagicMock()
        resp.output_active = True
        resp.output_paused = False
        resp.output_timecode = "00:01:30"
        resp.output_bytes = 1000000
        self.obs._client.get_record_status.return_value = resp
        status = self.obs.get_recording_status()
        assert status["active"] is True
        assert status["paused"] is False
        assert status["timecode"] == "00:01:30"
        assert status["bytes"] == 1000000


# ---------------------------------------------------------------------------
# Source visibility
# ---------------------------------------------------------------------------


class TestOBSSourceVisibility:
    def setup_method(self):
        self.obs = OBSController({})
        self.obs._client = MagicMock()

    def test_set_source_visibility(self):
        resp = MagicMock()
        resp.scene_item_id = 42
        self.obs._client.get_scene_item_id.return_value = resp
        self.obs.set_source_visibility("Scene1", "Source1", True)
        self.obs._client.set_scene_item_enabled.assert_called_once_with("Scene1", 42, True)

    def test_set_source_visibility_failure(self):
        self.obs._client.get_scene_item_id.side_effect = RuntimeError("not found")
        with pytest.raises(RuntimeError):
            self.obs.set_source_visibility("Scene1", "Missing", True)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


class TestOBSConvenience:
    def setup_method(self):
        self.obs = OBSController({
            "scenes": {
                "main": "Main",
                "intro_scene": "Intro",
                "outro_scene": "Outro",
                "diagram_overlay": "Diagram Overlay",
            }
        })
        self.obs._client = MagicMock()

    def test_transition_to_main(self):
        self.obs.transition_to_main()
        self.obs._client.set_current_program_scene.assert_called_once_with("Main")

    def test_transition_to_qgis_is_alias(self):
        assert OBSController.transition_to_qgis is OBSController.transition_to_main

    def test_transition_to_intro(self):
        self.obs.transition_to_intro()
        self.obs._client.set_current_program_scene.assert_called_once_with("Intro")

    def test_transition_to_outro(self):
        self.obs.transition_to_outro()
        self.obs._client.set_current_program_scene.assert_called_once_with("Outro")

    def test_show_diagram_overlay_true(self):
        self.obs.show_diagram_overlay(visible=True)
        self.obs._client.set_current_program_scene.assert_called_with("Diagram Overlay")

    def test_show_diagram_overlay_false(self):
        self.obs.show_diagram_overlay(visible=False)
        self.obs._client.set_current_program_scene.assert_called_with("Main")

    def test_show_diagram_overlay_default_names(self):
        obs = OBSController({"scenes": {}})
        obs._client = MagicMock()
        obs.show_diagram_overlay(visible=True)
        obs._client.set_current_program_scene.assert_called_with("Diagram Overlay")


# ---------------------------------------------------------------------------
# Wait for recording
# ---------------------------------------------------------------------------


class TestOBSWaitForRecording:
    @patch("video_automation.core.obs_controller.time.sleep")
    def test_wait_success(self, mock_sleep):
        obs = OBSController({})
        obs._client = MagicMock()
        resp = MagicMock()
        resp.output_active = True
        resp.output_paused = False
        obs._client.get_record_status.return_value = resp
        obs.wait_for_recording_start(timeout=5.0)

    @patch("video_automation.core.obs_controller.time.sleep")
    def test_wait_timeout(self, mock_sleep):
        obs = OBSController({})
        obs._client = MagicMock()
        resp = MagicMock()
        resp.output_active = False
        resp.output_paused = False
        obs._client.get_record_status.return_value = resp
        with pytest.raises(TimeoutError):
            obs.wait_for_recording_start(timeout=0.1, poll=0.01)
