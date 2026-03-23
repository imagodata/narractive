"""Tests for subtitle generation utilities."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from video_automation.core.subtitles import (
    SubtitleGenerator,
    count_words,
    estimate_duration,
    format_timestamp,
    generate_srt,
    split_into_subtitle_blocks,
)


class TestFormatTimestamp:
    def test_zero(self):
        assert format_timestamp(0) == "00:00:00,000"

    def test_full_timestamp(self):
        assert format_timestamp(3661.5) == "01:01:01,500"

    def test_millis(self):
        assert format_timestamp(0.123) == "00:00:00,123"

    def test_minutes(self):
        assert format_timestamp(90.0) == "00:01:30,000"


class TestCountWords:
    def test_simple(self):
        assert count_words("hello world") == 2

    def test_single_word(self):
        assert count_words("hello") == 1

    def test_empty(self):
        assert count_words("") == 0

    def test_extra_spaces(self):
        assert count_words("hello   world") == 2


class TestEstimateDuration:
    def test_basic_math(self):
        # 5 words at 150 wpm = 5/150 * 60 = 2.0 seconds
        text = "one two three four five"
        duration = estimate_duration(text, wpm=150)
        assert duration == pytest.approx(2.0, rel=0.01)

    def test_minimum_duration(self):
        # Very short text should hit minimum duration (1.5s)
        duration = estimate_duration("hi", wpm=150)
        assert duration >= 1.5

    def test_longer_text(self):
        # 150 words at 150 wpm = 60 seconds
        text = " ".join(["word"] * 150)
        duration = estimate_duration(text, wpm=150)
        assert duration == pytest.approx(60.0, rel=0.01)


class TestSplitIntoSubtitleBlocks:
    def test_empty_text(self):
        assert split_into_subtitle_blocks("") == []

    def test_whitespace_only(self):
        assert split_into_subtitle_blocks("   ") == []

    def test_simple_sentence(self):
        blocks = split_into_subtitle_blocks("Hello world.")
        assert len(blocks) >= 1
        assert all(isinstance(b, str) for b in blocks)

    def test_long_sentence_wraps(self):
        long_text = (
            "This is a very long sentence that should be split into multiple "
            "subtitle blocks because it exceeds the character limit per line."
        )
        blocks = split_into_subtitle_blocks(long_text, max_chars_per_line=42, max_lines=2)
        assert len(blocks) >= 1
        for block in blocks:
            lines = block.split("\n")
            assert len(lines) <= 2
            for line in lines:
                assert len(line) <= 42

    def test_multiple_sentences(self):
        text = "First sentence. Second sentence. Third sentence."
        blocks = split_into_subtitle_blocks(text)
        assert len(blocks) >= 2


class TestGenerateSrt:
    def test_produces_srt_format(self):
        text = "Hello world. This is a test."
        srt = generate_srt(text, wpm=150)
        assert isinstance(srt, str)
        # Should contain sequential block numbers
        assert "1\n" in srt
        # Should contain timestamp arrows
        assert " --> " in srt
        # Should contain the text content
        assert "Hello world" in srt

    def test_numbered_blocks(self):
        text = "First sentence. Second sentence. Third sentence."
        srt = generate_srt(text, wpm=150)
        lines = srt.strip().split("\n")
        # First non-empty line should be "1"
        non_empty = [line for line in lines if line.strip()]
        assert non_empty[0] == "1"

    def test_timestamp_format_in_srt(self):
        text = "Hello world."
        srt = generate_srt(text, wpm=150)
        # Timestamps should match HH:MM:SS,mmm --> HH:MM:SS,mmm pattern
        import re

        pattern = r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}"
        assert re.search(pattern, srt) is not None

    def test_empty_produces_empty(self):
        srt = generate_srt("", wpm=150)
        assert srt == ""


class TestSubtitleGenerator:
    def test_writes_file_to_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SubtitleGenerator({})
            out_path = Path(tmpdir) / "test.srt"
            result = gen.generate_for_sequence(
                "seq01",
                "Hello world. This is a test narration.",
                out_path,
                lang="en",
            )
            assert result == out_path
            assert out_path.exists()
            content = out_path.read_text(encoding="utf-8")
            assert " --> " in content

    def test_generate_for_language(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SubtitleGenerator({})
            narrations = {
                "seq01": "Hello world.",
                "seq02": "Second sequence text.",
            }
            results = gen.generate_for_language(narrations, Path(tmpdir), lang="en")
            assert len(results) == 2
            assert "seq01" in results
            assert "seq02" in results
            for path in results.values():
                assert path.exists()

    def test_skips_empty_narrations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SubtitleGenerator({})
            narrations = {
                "seq01": "Hello world.",
                "seq02": "",
                "seq03": "   ",
            }
            results = gen.generate_for_language(narrations, Path(tmpdir), lang="en")
            assert len(results) == 1
            assert "seq01" in results

    def test_custom_config(self):
        config = {"max_chars_per_line": 30, "max_lines": 1, "enabled": True}
        gen = SubtitleGenerator(config)
        assert gen.max_chars == 30
        assert gen.max_lines == 1
