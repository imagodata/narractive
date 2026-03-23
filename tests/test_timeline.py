"""Tests for the NarrationCue dataclass and TimelineExecutor."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from video_automation.core.timeline import NarrationCue, TimelineResult


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

    def test_label_auto_derived_from_text(self):
        cue = NarrationCue(text="Short text")
        assert cue.label == "Short text"

    def test_label_truncated_for_long_text(self):
        long_text = "A" * 100
        cue = NarrationCue(text=long_text)
        assert len(cue.label) <= 51  # 50 chars + ellipsis
        assert cue.label.endswith("…")

    def test_empty_text_no_label(self):
        cue = NarrationCue(text="")
        assert cue.label == ""

    def test_custom_label_overrides_auto(self):
        cue = NarrationCue(text="Some text", label="custom")
        assert cue.label == "custom"

    def test_audio_fields_default_none(self):
        cue = NarrationCue(text="Hello")
        assert cue._audio_path is None
        assert cue._audio_duration == 0.0

    def test_sync_modes(self):
        for mode in ("during", "before", "after"):
            cue = NarrationCue(text="test", sync=mode)
            assert cue.sync == mode


class TestTimelineResult:
    def test_construction(self):
        cues = [NarrationCue(text="Hello"), NarrationCue(text="World")]
        result = TimelineResult(
            cues=cues,
            total_duration=10.0,
            narration_timecodes=[],
        )
        assert result.total_duration == 10.0
        assert len(result.cues) == 2
        assert result.narration_timecodes == []

    def test_with_timecodes(self):
        from pathlib import Path

        result = TimelineResult(
            cues=[],
            total_duration=5.0,
            narration_timecodes=[(0.0, Path("/tmp/audio.mp3")), (2.5, Path("/tmp/audio2.mp3"))],
        )
        assert len(result.narration_timecodes) == 2
        assert result.narration_timecodes[0][0] == 0.0
