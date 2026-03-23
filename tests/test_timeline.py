"""Tests for the NarrationCue dataclass and TimelineExecutor."""

from __future__ import annotations

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
        def action():
            return None

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

    def test_sync_during(self):
        cue = NarrationCue(text="Hello", sync="during")
        assert cue.sync == "during"

    def test_sync_before(self):
        cue = NarrationCue(text="Hello", sync="before")
        assert cue.sync == "before"

    def test_sync_after(self):
        cue = NarrationCue(text="Hello", sync="after")
        assert cue.sync == "after"

    def test_label_auto_derived_from_text(self):
        cue = NarrationCue(text="Short text")
        assert cue.label == "Short text"

    def test_label_truncated_for_long_text(self):
        long_text = "A" * 60
        cue = NarrationCue(text=long_text)
        assert cue.label.endswith("…")
        assert len(cue.label) <= 51  # 50 chars + ellipsis

    def test_custom_label_overrides_auto(self):
        cue = NarrationCue(text="Some text", label="custom_label")
        assert cue.label == "custom_label"

    def test_silent_cue_has_no_label(self):
        cue = NarrationCue(text="")
        assert cue.label == ""
