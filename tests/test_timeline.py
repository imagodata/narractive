"""Tests for NarrationCue, TimelineExecutor, and TimelineResult."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from narractive.core.timeline import NarrationCue, TimelineExecutor, TimelineResult


# ---------------------------------------------------------------------------
# NarrationCue
# ---------------------------------------------------------------------------


class TestNarrationCue:
    def test_default_values(self):
        cue = NarrationCue(text="Hello")
        assert cue.text == "Hello"
        assert cue.actions is None
        assert cue.sync == "during"
        assert cue.pre_delay == 0.0
        assert cue.post_delay == 0.5
        assert cue.label == "Hello"
        assert cue.scene is None

    def test_custom_values(self):
        action = lambda: None
        cue = NarrationCue(
            text="Test",
            actions=action,
            sync="before",
            pre_delay=0.5,
            post_delay=1.0,
            label="my_cue",
            scene="Custom Scene",
        )
        assert cue.sync == "before"
        assert cue.pre_delay == 0.5
        assert cue.post_delay == 1.0
        assert cue.label == "my_cue"
        assert cue.scene == "Custom Scene"
        assert cue.actions is action

    def test_empty_text_is_silent_cue(self):
        cue = NarrationCue(text="")
        assert cue.text == ""
        assert cue.label == ""

    def test_label_auto_derived_from_short_text(self):
        cue = NarrationCue(text="Short text")
        assert cue.label == "Short text"

    def test_label_auto_derived_from_long_text(self):
        long_text = "A" * 100
        cue = NarrationCue(text=long_text)
        assert len(cue.label) <= 55  # 50 chars + ellipsis

    def test_label_not_overridden_when_explicit(self):
        cue = NarrationCue(text="Some text", label="Custom Label")
        assert cue.label == "Custom Label"

    def test_audio_path_defaults_none(self):
        cue = NarrationCue(text="Test")
        assert cue._audio_path is None
        assert cue._audio_duration == 0.0

    def test_valid_sync_values(self):
        for mode in ("during", "before", "after"):
            cue = NarrationCue(text="test", sync=mode)
            assert cue.sync == mode


# ---------------------------------------------------------------------------
# TimelineResult
# ---------------------------------------------------------------------------


class TestTimelineResult:
    def test_creation(self):
        cues = [NarrationCue(text="A"), NarrationCue(text="B")]
        result = TimelineResult(
            cues=cues,
            total_duration=10.5,
            narration_timecodes=[(0.0, Path("a.mp3")), (5.0, Path("b.mp3"))],
        )
        assert result.total_duration == 10.5
        assert len(result.cues) == 2
        assert len(result.narration_timecodes) == 2


# ---------------------------------------------------------------------------
# TimelineExecutor
# ---------------------------------------------------------------------------


class TestTimelineExecutor:
    @pytest.fixture
    def mock_narrator(self, tmp_path):
        narrator = MagicMock()
        narrator.get_narration_duration = MagicMock(return_value=2.0)
        # generate_narration returns the path and creates it
        def fake_generate(text, path):
            Path(path).touch()
            return Path(path)
        narrator.generate_narration = MagicMock(side_effect=fake_generate)
        return narrator

    @pytest.fixture
    def executor(self, mock_narrator, tmp_path):
        return TimelineExecutor(
            narrator=mock_narrator,
            sequence_id="test_seq",
            cache_dir=tmp_path / "segments",
            play_audio=False,
        )

    def test_init(self, executor, tmp_path):
        assert executor.sequence_id == "test_seq"
        assert executor.play_audio is False
        assert (tmp_path / "segments").is_dir()

    def test_prepare_empty_cues(self, executor):
        executor.prepare([])
        # No error should occur

    def test_prepare_generates_audio(self, executor, mock_narrator):
        cues = [NarrationCue(text="Hello world")]
        executor.prepare(cues)
        mock_narrator.generate_narration.assert_called_once()
        assert cues[0]._audio_duration == 2.0
        assert cues[0]._audio_path is not None

    def test_prepare_silent_cue_skipped(self, executor, mock_narrator):
        cues = [NarrationCue(text="")]
        executor.prepare(cues)
        mock_narrator.generate_narration.assert_not_called()
        assert cues[0]._audio_duration == 0.0
        assert cues[0]._audio_path is None

    def test_prepare_uses_cache(self, executor, mock_narrator, tmp_path):
        # Pre-create cached file
        cache_file = tmp_path / "segments" / "test_seq_cue00.mp3"
        cache_file.touch()
        cues = [NarrationCue(text="Hello")]
        executor.prepare(cues)
        # Should use cached file, not regenerate
        mock_narrator.generate_narration.assert_not_called()
        mock_narrator.get_narration_duration.assert_called_once_with(cache_file)

    @patch("time.sleep")
    def test_execute_during_mode(self, mock_sleep, executor):
        action_called = []
        cue = NarrationCue(
            text="Test",
            actions=lambda: action_called.append(True),
            sync="during",
            pre_delay=0.0,
            post_delay=0.0,
        )
        cue._audio_path = Path("fake.mp3")
        cue._audio_duration = 1.0

        result = executor.execute([cue])
        assert len(action_called) == 1
        assert isinstance(result, TimelineResult)
        assert len(result.narration_timecodes) == 1

    @patch("time.sleep")
    def test_execute_before_mode(self, mock_sleep, executor):
        action_called = []
        cue = NarrationCue(
            text="Test",
            actions=lambda: action_called.append(True),
            sync="before",
            pre_delay=0.0,
            post_delay=0.0,
        )
        cue._audio_path = Path("fake.mp3")
        cue._audio_duration = 1.0

        result = executor.execute([cue])
        assert len(action_called) == 1
        assert len(result.narration_timecodes) == 1

    @patch("time.sleep")
    def test_execute_after_mode(self, mock_sleep, executor):
        action_called = []
        cue = NarrationCue(
            text="Test",
            actions=lambda: action_called.append(True),
            sync="after",
            pre_delay=0.0,
            post_delay=0.0,
        )
        cue._audio_path = Path("fake.mp3")
        cue._audio_duration = 1.0

        result = executor.execute([cue])
        assert len(action_called) == 1
        assert len(result.narration_timecodes) == 1

    @patch("time.sleep")
    def test_execute_with_pre_delay(self, mock_sleep, executor):
        cue = NarrationCue(text="", pre_delay=2.0, post_delay=0.0)
        executor.execute([cue])
        mock_sleep.assert_any_call(2.0)

    @patch("time.sleep")
    def test_execute_with_post_delay(self, mock_sleep, executor):
        cue = NarrationCue(text="", pre_delay=0.0, post_delay=1.5)
        executor.execute([cue])
        mock_sleep.assert_any_call(1.5)

    @patch("time.sleep")
    def test_execute_scene_switch(self, mock_sleep, executor):
        obs = MagicMock()
        cue = NarrationCue(text="", scene="Diagram", pre_delay=0.0, post_delay=0.0)
        executor.execute([cue], obs=obs)
        obs.switch_scene.assert_called_once_with("Diagram")

    @patch("time.sleep")
    def test_execute_scene_switch_failure_is_warning(self, mock_sleep, executor):
        obs = MagicMock()
        obs.switch_scene.side_effect = RuntimeError("OBS down")
        cue = NarrationCue(text="", scene="Broken", pre_delay=0.0, post_delay=0.0)
        # Should not raise
        executor.execute([cue], obs=obs)

    @patch("time.sleep")
    def test_execute_action_failure_is_logged(self, mock_sleep, executor):
        def bad_action():
            raise ValueError("boom")
        cue = NarrationCue(
            text="",
            actions=bad_action,
            pre_delay=0.0,
            post_delay=0.0,
        )
        # Should not raise
        executor.execute([cue])

    @patch("time.sleep")
    def test_execute_silent_cue_no_timecodes(self, mock_sleep, executor):
        cue = NarrationCue(text="", pre_delay=0.0, post_delay=0.0)
        result = executor.execute([cue])
        assert len(result.narration_timecodes) == 0

    @patch("time.sleep")
    def test_execute_multiple_cues(self, mock_sleep, executor):
        cues = [
            NarrationCue(text="", pre_delay=0.0, post_delay=0.0),
            NarrationCue(text="", pre_delay=0.0, post_delay=0.0),
            NarrationCue(text="", pre_delay=0.0, post_delay=0.0),
        ]
        result = executor.execute(cues)
        assert result.total_duration >= 0
        assert len(result.cues) == 3

    def test_get_total_estimated_duration(self, executor):
        cues = [
            NarrationCue(text="", pre_delay=1.0, post_delay=0.5),
            NarrationCue(text="", pre_delay=0.0, post_delay=1.0),
        ]
        cues[0]._audio_duration = 3.0
        cues[1]._audio_duration = 2.0
        total = executor.get_total_estimated_duration(cues)
        # 1.0 + 3.0 + 0.5 + 0.0 + 2.0 + 1.0 = 7.5
        assert total == 7.5

    def test_get_total_estimated_duration_empty(self, executor):
        assert executor.get_total_estimated_duration([]) == 0.0
