"""Tests for the subtitle generator module."""
from __future__ import annotations

from video_automation.core.subtitles import (
    MIN_DURATION,
    count_words,
    estimate_duration,
    format_timestamp,
    generate_srt,
    split_into_subtitle_blocks,
)


class TestCountWords:
    def test_simple(self):
        assert count_words("hello world") == 2

    def test_empty(self):
        assert count_words("") == 0

    def test_multiple_spaces(self):
        assert count_words("hello   world   test") == 3


class TestFormatTimestamp:
    def test_zero(self):
        assert format_timestamp(0.0) == "00:00:00,000"

    def test_simple_seconds(self):
        assert format_timestamp(1.5) == "00:00:01,500"

    def test_minutes(self):
        assert format_timestamp(65.0) == "00:01:05,000"

    def test_hours(self):
        assert format_timestamp(3661.123) == "01:01:01,123"

    def test_milliseconds_precision(self):
        ts = format_timestamp(1.234)
        assert ts == "00:00:01,234"


class TestEstimateDuration:
    def test_basic_estimate(self):
        # 155 words at 155 WPM = 60 seconds
        text = " ".join(["word"] * 155)
        duration = estimate_duration(text, wpm=155)
        assert abs(duration - 60.0) < 0.1

    def test_minimum_duration(self):
        duration = estimate_duration("short", wpm=155)
        assert duration == MIN_DURATION

    def test_empty_text(self):
        duration = estimate_duration("", wpm=155)
        assert duration == MIN_DURATION

    def test_newlines_handled(self):
        text = "hello\nworld\ntest"
        duration = estimate_duration(text, wpm=155)
        assert duration >= MIN_DURATION


class TestSplitIntoSubtitleBlocks:
    def test_empty_text(self):
        assert split_into_subtitle_blocks("") == []

    def test_whitespace_only(self):
        assert split_into_subtitle_blocks("   ") == []

    def test_short_sentence(self):
        blocks = split_into_subtitle_blocks("Hello world.")
        assert len(blocks) == 1
        assert blocks[0] == "Hello world."

    def test_multiple_sentences(self):
        text = "First sentence. Second sentence. Third sentence."
        blocks = split_into_subtitle_blocks(text)
        assert len(blocks) == 3

    def test_long_sentence_wrapping(self):
        text = "This is a very long sentence that should be wrapped across multiple lines in the subtitle block."
        blocks = split_into_subtitle_blocks(text, max_chars_per_line=30, max_lines=2)
        assert len(blocks) >= 1
        for block in blocks:
            lines = block.split("\n")
            assert len(lines) <= 2

    def test_respects_max_chars(self):
        text = "Short. Another short one."
        blocks = split_into_subtitle_blocks(text, max_chars_per_line=42)
        for block in blocks:
            for line in block.split("\n"):
                assert len(line) <= 42


class TestGenerateSrt:
    def test_basic_output(self):
        srt = generate_srt("Hello world.", wpm=155)
        assert "1\n" in srt
        assert "-->" in srt
        assert "Hello world." in srt

    def test_empty_text(self):
        srt = generate_srt("", wpm=155)
        assert srt == ""

    def test_multiple_paragraphs(self):
        text = "First paragraph.\n\nSecond paragraph."
        srt = generate_srt(text, wpm=155)
        assert "1\n" in srt
        assert "2\n" in srt

    def test_srt_index_sequential(self):
        text = "Sentence one. Sentence two. Sentence three."
        srt = generate_srt(text, wpm=155)
        lines = srt.strip().split("\n")
        indices = [int(line) for line in lines if line.strip().isdigit()]
        assert indices == list(range(1, len(indices) + 1))

    def test_timestamps_increasing(self):
        text = "First sentence. Second sentence. Third sentence."
        srt = generate_srt(text, wpm=155)
        timestamps = []
        for line in srt.split("\n"):
            if "-->" in line:
                start, end = line.split(" --> ")
                timestamps.append((start.strip(), end.strip()))
        # Each start should be >= previous end
        for i in range(1, len(timestamps)):
            assert timestamps[i][0] >= timestamps[i - 1][1]

    def test_very_long_text(self):
        text = "This is a test sentence. " * 50
        srt = generate_srt(text, wpm=155)
        assert srt
        assert srt.count("-->") >= 10
