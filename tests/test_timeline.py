"""Tests for the NarrationCue dataclass and TimelineExecutor."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from video_automation.core.timeline import NarrationCue


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
