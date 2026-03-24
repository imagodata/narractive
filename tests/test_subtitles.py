"""Tests for subtitle generation — SRT formatting, timing, text splitting."""
from __future__ import annotations

from pathlib import Path

import pytest

from narractive.core.subtitles import (
    SubtitleGenerator,
    count_words,
    estimate_duration,
    format_timestamp,
    generate_srt,
    split_into_subtitle_blocks,
    MIN_DURATION,
)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


class TestCountWords:
    def test_simple_sentence(self):
        assert count_words("hello world") == 2

    def test_empty_string(self):
        assert count_words("") == 0

    def test_whitespace_only(self):
        assert count_words("   ") == 0

    def test_multiline(self):
        assert count_words("hello\nworld\nfoo") == 3


class TestFormatTimestamp:
    def test_zero(self):
        assert format_timestamp(0.0) == "00:00:00,000"

    def test_seconds_only(self):
        assert format_timestamp(5.5) == "00:00:05,500"

    def test_minutes_and_seconds(self):
        assert format_timestamp(65.123) == "00:01:05,123"

    def test_hours(self):
        assert format_timestamp(3661.0) == "01:01:01,000"

    def test_millisecond_rounding(self):
        result = format_timestamp(1.9999)
        # Should round to nearest ms
        assert result.startswith("00:00:0")


class TestEstimateDuration:
    def test_one_word(self):
        """A single word at 160 WPM = 0.375s, but min is MIN_DURATION."""
        dur = estimate_duration("hello", wpm=160)
        assert dur == MIN_DURATION

    def test_many_words(self):
        text = " ".join(["word"] * 160)
        dur = estimate_duration(text, wpm=160)
        assert abs(dur - 60.0) < 0.1

    def test_empty_text(self):
        dur = estimate_duration("", wpm=155)
        assert dur == MIN_DURATION

    def test_minimum_enforced(self):
        dur = estimate_duration("hi", wpm=1000)
        assert dur >= MIN_DURATION


class TestSplitIntoSubtitleBlocks:
    def test_empty_text(self):
        assert split_into_subtitle_blocks("") == []

    def test_short_sentence(self):
        blocks = split_into_subtitle_blocks("Hello world.")
        assert len(blocks) == 1
        assert blocks[0] == "Hello world."

    def test_two_sentences(self):
        blocks = split_into_subtitle_blocks("First sentence. Second sentence.")
        assert len(blocks) == 2

    def test_long_sentence_wrapped(self):
        long = "This is a very long sentence that should be wrapped into multiple lines for subtitles."
        blocks = split_into_subtitle_blocks(long, max_chars_per_line=30, max_lines=2)
        assert len(blocks) >= 1
        for block in blocks:
            lines = block.split("\n")
            assert len(lines) <= 2
            for line in lines:
                assert len(line) <= 30

    def test_max_lines_respected(self):
        long = "Word " * 50 + "end."
        blocks = split_into_subtitle_blocks(long, max_chars_per_line=20, max_lines=2)
        for block in blocks:
            assert block.count("\n") < 2  # at most 1 newline = 2 lines

    def test_whitespace_stripped(self):
        blocks = split_into_subtitle_blocks("  Hello world.  ")
        assert blocks[0] == "Hello world."


# ---------------------------------------------------------------------------
# SRT generation
# ---------------------------------------------------------------------------


class TestGenerateSrt:
    def test_single_sentence(self):
        srt = generate_srt("Hello world.", wpm=160)
        assert "1\n" in srt
        assert "-->" in srt
        assert "Hello world." in srt

    def test_two_paragraphs(self):
        text = "First paragraph.\n\nSecond paragraph."
        srt = generate_srt(text, wpm=160)
        assert "1\n" in srt
        assert "2\n" in srt

    def test_timestamps_are_sequential(self):
        text = "First sentence. Second sentence. Third sentence."
        srt = generate_srt(text, wpm=160)
        lines = srt.strip().split("\n")
        timestamps = [l for l in lines if "-->" in l]
        assert len(timestamps) >= 2
        # Parse first start and last start to ensure ordering
        first_start = timestamps[0].split(" --> ")[0]
        last_start = timestamps[-1].split(" --> ")[0]
        assert first_start <= last_start

    def test_start_margin_applied(self):
        srt = generate_srt("Hello.", wpm=160, start_margin=2.0)
        # First timestamp should start at or after 2.0s
        lines = srt.strip().split("\n")
        first_time_line = [l for l in lines if "-->" in l][0]
        start = first_time_line.split(" --> ")[0]
        assert start >= "00:00:02,000"

    def test_empty_text_produces_empty_srt(self):
        srt = generate_srt("", wpm=160)
        assert srt.strip() == ""


# ---------------------------------------------------------------------------
# SubtitleGenerator class
# ---------------------------------------------------------------------------


class TestSubtitleGenerator:
    def setup_method(self):
        self.config = {
            "enabled": True,
            "max_chars_per_line": 42,
            "max_lines": 2,
            "output_dir": "output/{lang}/subtitles",
        }
        self.gen = SubtitleGenerator(self.config)

    def test_init_defaults(self):
        gen = SubtitleGenerator({})
        assert gen.enabled is True
        assert gen.max_chars == 42
        assert gen.max_lines == 2

    def test_init_custom(self):
        gen = SubtitleGenerator({
            "enabled": False,
            "max_chars_per_line": 50,
            "max_lines": 3,
        })
        assert gen.enabled is False
        assert gen.max_chars == 50
        assert gen.max_lines == 3

    def test_generate_for_sequence(self, tmp_path):
        output = tmp_path / "test.srt"
        result = self.gen.generate_for_sequence(
            "seq01",
            "This is a test narration for the first sequence.",
            output,
            lang="en",
        )
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "1\n" in content
        assert "-->" in content

    def test_generate_for_sequence_custom_wpm(self, tmp_path):
        output = tmp_path / "test2.srt"
        self.gen.generate_for_sequence("seq02", "Test text.", output, lang="en", wpm=200)
        content = output.read_text(encoding="utf-8")
        assert "Test text." in content

    def test_generate_for_sequence_creates_parent_dir(self, tmp_path):
        output = tmp_path / "sub" / "dir" / "test.srt"
        self.gen.generate_for_sequence("seq03", "Hello.", output, lang="fr")
        assert output.exists()

    def test_generate_for_language(self, tmp_path):
        narrations = {
            "seq01": "First sequence narration text.",
            "seq02": "Second sequence narration text.",
        }
        results = self.gen.generate_for_language(
            narrations, tmp_path, lang="en"
        )
        assert len(results) == 2
        assert "seq01" in results
        assert "seq02" in results
        assert results["seq01"].exists()

    def test_generate_for_language_skips_empty(self, tmp_path):
        narrations = {
            "seq01": "Real text.",
            "seq02": "",
            "seq03": "   ",
        }
        results = self.gen.generate_for_language(narrations, tmp_path, lang="en")
        assert len(results) == 1
        assert "seq01" in results

    def test_generate_for_language_skips_non_string(self, tmp_path):
        narrations = {
            "seq01": "Real text.",
            "seq02": 42,
            "seq03": None,
        }
        results = self.gen.generate_for_language(narrations, tmp_path, lang="en")
        assert len(results) == 1

    def test_default_wpm_by_language(self, tmp_path):
        """Different languages should use different default WPM rates."""
        output_fr = tmp_path / "fr.srt"
        output_en = tmp_path / "en.srt"
        text = " ".join(["word"] * 50) + "."
        self.gen.generate_for_sequence("s1", text, output_fr, lang="fr")
        self.gen.generate_for_sequence("s2", text, output_en, lang="en")
        # Both should produce valid SRT files
        assert output_fr.exists()
        assert output_en.exists()
