"""Tests for the Recorder Protocol and VideoSequence base classes."""
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


# ---------------------------------------------------------------------------
# Tests
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

    def test_repr(self):
        seq = ConcreteSequence()
        assert "Test Sequence" in repr(seq)

    def test_setup_switches_scene(self):
        seq = ConcreteSequence()
        seq.setup(self.obs, self.app, self.config)
        assert self.obs.current_scene == "Main"
        self.app.focus_app.assert_called_once()

    def test_run_calls_lifecycle(self):
        seq = ConcreteSequence()
        seq.setup = MagicMock()
        seq.teardown = MagicMock()
        seq.execute = MagicMock()
        seq.run(self.obs, self.app, self.config)
        seq.setup.assert_called_once()
        seq.execute.assert_called_once()
        seq.teardown.assert_called_once()

    def test_elapsed_time(self):
        seq = ConcreteSequence()
        seq._start_time = time.time() - 5.0
        assert 4.9 <= seq.elapsed() <= 6.0

    @patch("time.sleep")
    def test_show_diagram(self, mock_sleep):
        seq = ConcreteSequence()
        seq.show_diagram(self.obs, "test_diagram", duration=3.0)
        # Should switch to overlay then back
        assert self.obs.current_scene == "Main"
        mock_sleep.assert_called_once_with(3.0)

    def test_edit_config_value_missing_region(self):
        pytest.importorskip("pyautogui")
        seq = ConcreteSequence()
        result = seq.edit_config_value(self.app, self.config, "nonexistent", "value")
        assert result is False

    def test_elapsed_zero_before_run(self):
        seq = ConcreteSequence()
        assert seq.elapsed() == 0.0

    @patch("time.sleep")
    def test_teardown_logs_elapsed(self, mock_sleep):
        seq = ConcreteSequence()
        seq._start_time = time.time()
        seq.teardown(self.obs, self.app, self.config)
        mock_sleep.assert_called_once_with(0.0)

    @patch("time.sleep")
    def test_show_diagram_and_return(self, mock_sleep):
        seq = ConcreteSequence()
        seq.show_diagram_and_return(self.obs, self.app, "diag1", duration=2.0)
        self.app.focus_panel.assert_called_once()


class TestTimelineSequence:
    def test_build_timeline_not_implemented(self):
        class IncompleteSeq(TimelineSequence):
            name = "Incomplete"
            sequence_id = "inc"

        seq = IncompleteSeq()
        with pytest.raises(NotImplementedError):
            seq.build_timeline(MagicMock(), MagicMock(), {})

    def test_timeline_sequence_is_video_sequence(self):
        assert issubclass(TimelineSequence, VideoSequence)

    def test_play_audio_default_false(self):
        class MySeq(TimelineSequence):
            name = "Test"
            sequence_id = "t"
            def build_timeline(self, obs, app, config):
                return []

        seq = MySeq()
        assert seq.play_audio is False

    def test_timeline_result_initially_none(self):
        class MySeq(TimelineSequence):
            name = "Test"
            sequence_id = "t"
            def build_timeline(self, obs, app, config):
                return []

        seq = MySeq()
        assert seq.timeline_result is None
