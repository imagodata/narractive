"""Tests for VideoSequence, TimelineSequence, and Recorder Protocol."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from video_automation.sequences.base import Recorder, TimelineSequence, VideoSequence


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

class FakeRecorder:
    """Minimal implementation satisfying the Recorder Protocol."""

    def __init__(self):
        self.connected = False
        self.recording = False
        self.current_scene = "Main"
        self.scenes = {"main": "Main", "diagram_overlay": "Diagram Overlay"}

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def start_recording(self):
        self.recording = True

    def stop_recording(self):
        self.recording = False
        return None

    def pause_recording(self):
        pass

    def resume_recording(self):
        pass

    def wait_for_recording_start(self, timeout=10.0):
        pass

    def switch_scene(self, scene_name):
        self.current_scene = scene_name

    def get_current_scene(self):
        return self.current_scene

    def show_diagram_overlay(self, visible=True):
        if visible:
            self.current_scene = "Diagram Overlay"
        else:
            self.current_scene = "Main"

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()


class ConcreteSequence(VideoSequence):
    """Concrete test implementation."""
    name = "Test Sequence"
    sequence_id = "test_seq"
    duration_estimate = 5.0
    narration_text = "Test narration."
    obs_scene = "Main"

    def execute(self, obs, app, config):
        pass


class TrackingSequence(VideoSequence):
    """Tracks lifecycle calls in order."""
    name = "Tracking"
    sequence_id = "track"

    def __init__(self):
        super().__init__()
        self.call_order = []

    def setup(self, obs, app, config):
        self.call_order.append("setup")

    def execute(self, obs, app, config):
        self.call_order.append("execute")

    def teardown(self, obs, app, config):
        self.call_order.append("teardown")


class FailingSequence(VideoSequence):
    """Execute raises an exception."""
    name = "Failing"
    sequence_id = "fail"

    def execute(self, obs, app, config):
        raise RuntimeError("execution failed")


# ---------------------------------------------------------------------------
# Tests: Recorder Protocol
# ---------------------------------------------------------------------------


class TestRecorderProtocol:
    def test_fake_recorder_satisfies_protocol(self):
        recorder = FakeRecorder()
        assert isinstance(recorder, Recorder)

    def test_context_manager(self):
        recorder = FakeRecorder()
        with recorder as r:
            assert r.connected
            r.start_recording()
            assert r.recording
            r.stop_recording()
            assert not r.recording
        assert not recorder.connected

    def test_scene_switching(self):
        recorder = FakeRecorder()
        recorder.switch_scene("Custom")
        assert recorder.get_current_scene() == "Custom"

    def test_diagram_overlay_toggle(self):
        recorder = FakeRecorder()
        recorder.show_diagram_overlay(True)
        assert recorder.get_current_scene() == "Diagram Overlay"
        recorder.show_diagram_overlay(False)
        assert recorder.get_current_scene() == "Main"


# ---------------------------------------------------------------------------
# Tests: VideoSequence
# ---------------------------------------------------------------------------


class TestVideoSequence:
    def setup_method(self):
        self.obs = FakeRecorder()
        self.app = MagicMock()
        self.app.focus_app = MagicMock()
        self.config = {
            "timing": {"transition_pause": 0.0, "mouse_move_duration": 0.1},
            "app": {"regions": {}},
        }

    def test_class_attributes(self):
        seq = ConcreteSequence()
        assert seq.name == "Test Sequence"
        assert seq.sequence_id == "test_seq"
        assert seq.obs_scene == "Main"
        assert seq.duration_estimate == 5.0

    def test_repr(self):
        seq = ConcreteSequence()
        r = repr(seq)
        assert "Test Sequence" in r
        assert "5s" in r

    def test_setup_switches_scene(self):
        seq = ConcreteSequence()
        seq.setup(self.obs, self.app, self.config)
        assert self.obs.current_scene == "Main"
        self.app.focus_app.assert_called_once()

    def test_setup_handles_scene_switch_failure(self):
        obs = MagicMock()
        obs.switch_scene.side_effect = RuntimeError("scene error")
        seq = ConcreteSequence()
        # Should not raise
        seq.setup(obs, self.app, self.config)

    def test_run_calls_lifecycle_in_order(self):
        seq = TrackingSequence()
        seq.run(self.obs, self.app, self.config)
        assert seq.call_order == ["setup", "execute", "teardown"]

    def test_teardown_called_even_on_failure(self):
        seq = FailingSequence()
        seq.teardown = MagicMock()
        with pytest.raises(RuntimeError):
            seq.run(self.obs, self.app, self.config)
        seq.teardown.assert_called_once()

    def test_elapsed_time(self):
        seq = ConcreteSequence()
        seq._start_time = time.time() - 5.0
        assert 4.9 <= seq.elapsed() <= 6.0

    def test_elapsed_zero_before_start(self):
        seq = ConcreteSequence()
        assert seq.elapsed() == 0.0

    @patch("time.sleep")
    def test_show_diagram(self, mock_sleep):
        seq = ConcreteSequence()
        seq.show_diagram(self.obs, "test_diagram", duration=3.0)
        assert self.obs.current_scene == "Main"
        mock_sleep.assert_called_once_with(3.0)

    @patch("time.sleep")
    def test_show_diagram_and_return(self, mock_sleep):
        seq = ConcreteSequence()
        seq.show_diagram_and_return(self.obs, self.app, "diag1", duration=2.0)
        self.app.focus_panel.assert_called_once()

    def test_edit_config_value_missing_region(self):
        pyautogui = pytest.importorskip("pyautogui")
        seq = ConcreteSequence()
        result = seq.edit_config_value(self.app, self.config, "nonexistent", "value")
        assert result is False

    def test_timeline_result_initially_none(self):
        seq = ConcreteSequence()
        assert seq.timeline_result is None

    def test_abstract_execute_not_instantiable(self):
        with pytest.raises(TypeError):
            VideoSequence()


# ---------------------------------------------------------------------------
# Tests: TimelineSequence
# ---------------------------------------------------------------------------


class TestTimelineSequence:
    def test_build_timeline_not_implemented(self):
        class BareTimeline(TimelineSequence):
            name = "Bare"
            sequence_id = "bare"
        seq = BareTimeline()
        with pytest.raises(NotImplementedError):
            seq.build_timeline(MagicMock(), MagicMock(), {})

    def test_play_audio_default_false(self):
        class TS(TimelineSequence):
            name = "TS"
            sequence_id = "ts"
            def build_timeline(self, obs, app, config):
                return []
        assert TS.play_audio is False

    def test_execute_with_empty_cues(self):
        class EmptyTimeline(TimelineSequence):
            name = "Empty"
            sequence_id = "empty"
            def build_timeline(self, obs, app, config):
                return []
        seq = EmptyTimeline()
        config = {"narration": {"output_dir": "/tmp/test_narr"}}
        # Should handle empty cues gracefully
        seq.execute(MagicMock(), MagicMock(), config)
        assert seq.timeline_result is None
