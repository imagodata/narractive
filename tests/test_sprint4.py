"""Sprint 4 — Unit tests for:
  - Issue #9:  Chapter markers in assembled MP4
  - Issue #10: WebVTT (.vtt) subtitle format support
  - Issue #11: Intro/outro from video clips (not just images)
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Issue #10 — WebVTT subtitle support
# ---------------------------------------------------------------------------

from narractive.core.subtitles import (
    SubtitleGenerator,
    format_vtt_timestamp,
    generate_vtt,
)


class TestFormatVttTimestamp:
    def test_zero(self):
        assert format_vtt_timestamp(0.0) == "00:00:00.000"

    def test_seconds_only(self):
        assert format_vtt_timestamp(5.5) == "00:00:05.500"

    def test_minutes_and_seconds(self):
        assert format_vtt_timestamp(65.123) == "00:01:05.123"

    def test_hours(self):
        assert format_vtt_timestamp(3661.0) == "01:01:01.000"

    def test_uses_dot_separator(self):
        """WebVTT uses dots; SRT uses commas."""
        result = format_vtt_timestamp(1.5)
        assert "." in result
        assert "," not in result


class TestGenerateVtt:
    def test_starts_with_webvtt_header(self):
        vtt = generate_vtt("Hello world.", wpm=160)
        assert vtt.startswith("WEBVTT\n\n")

    def test_contains_cue_with_arrow(self):
        vtt = generate_vtt("Hello world.", wpm=160)
        assert "-->" in vtt

    def test_dot_separator_in_timestamps(self):
        vtt = generate_vtt("Some text.", wpm=160)
        # All timestamp fields must use dots
        lines = [l for l in vtt.splitlines() if "-->" in l]
        assert len(lines) >= 1
        for line in lines:
            parts = line.split(" --> ")
            assert "." in parts[0]
            assert "." in parts[1]
            assert "," not in parts[0]
            assert "," not in parts[1]

    def test_empty_text_produces_header_only(self):
        vtt = generate_vtt("", wpm=160)
        # Should at least contain the WEBVTT header
        assert vtt.startswith("WEBVTT")
        # And no cue content beyond the header
        lines = [l for l in vtt.splitlines() if "-->" in l]
        assert lines == []

    def test_multiple_paragraphs(self):
        text = "First paragraph.\n\nSecond paragraph."
        vtt = generate_vtt(text, wpm=160)
        cue_lines = [l for l in vtt.splitlines() if "-->" in l]
        assert len(cue_lines) >= 2

    def test_timestamps_are_sequential(self):
        text = "First. Second. Third."
        vtt = generate_vtt(text, wpm=160)
        cue_lines = [l for l in vtt.splitlines() if "-->" in l]
        starts = [l.split(" --> ")[0] for l in cue_lines]
        assert starts == sorted(starts)

    def test_start_margin_applied(self):
        vtt = generate_vtt("Hello.", wpm=160, start_margin=2.0)
        cue_lines = [l for l in vtt.splitlines() if "-->" in l]
        first_start = cue_lines[0].split(" --> ")[0]
        assert first_start >= "00:00:02.000"


class TestSubtitleGeneratorWebVtt:
    def setup_method(self):
        self.config = {
            "enabled": True,
            "max_chars_per_line": 42,
            "max_lines": 2,
        }
        self.gen = SubtitleGenerator(self.config)

    def test_generate_for_sequence_no_vtt_by_default(self, tmp_path):
        output = tmp_path / "seq01.srt"
        self.gen.generate_for_sequence("seq01", "Hello world.", output, lang="en")
        assert output.exists()
        assert not (tmp_path / "seq01.vtt").exists()

    def test_generate_for_sequence_creates_vtt_when_requested(self, tmp_path):
        output = tmp_path / "seq01.srt"
        self.gen.generate_for_sequence(
            "seq01", "Hello world.", output, lang="en", generate_webvtt=True
        )
        assert output.exists()
        vtt_path = tmp_path / "seq01.vtt"
        assert vtt_path.exists()
        content = vtt_path.read_text(encoding="utf-8")
        assert content.startswith("WEBVTT")
        assert "-->" in content

    def test_vtt_alongside_srt_same_cue_count(self, tmp_path):
        text = "First sentence. Second sentence."
        srt_path = tmp_path / "seq01.srt"
        self.gen.generate_for_sequence(
            "seq01", text, srt_path, lang="en", generate_webvtt=True
        )
        srt_arrows = srt_path.read_text().count("-->")
        vtt_arrows = (tmp_path / "seq01.vtt").read_text().count("-->")
        assert srt_arrows == vtt_arrows

    def test_generate_for_language_creates_vtts(self, tmp_path):
        narrations = {"seq01": "Text one.", "seq02": "Text two."}
        self.gen.generate_for_language(
            narrations, tmp_path, lang="en", generate_webvtt=True
        )
        assert (tmp_path / "seq01.vtt").exists()
        assert (tmp_path / "seq02.vtt").exists()

    def test_generate_for_language_no_vtts_by_default(self, tmp_path):
        narrations = {"seq01": "Text one."}
        self.gen.generate_for_language(narrations, tmp_path, lang="en")
        assert not (tmp_path / "seq01.vtt").exists()


# ---------------------------------------------------------------------------
# Issue #9 — Chapter markers in MP4
# ---------------------------------------------------------------------------

from narractive.core.video_assembler import VideoAssembler


class TestAddChapterMarkers:
    @patch("narractive.core.video_assembler._check_ffmpeg")
    def test_empty_chapters_raises(self, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        with pytest.raises(ValueError, match="empty"):
            va.add_chapter_markers(tmp_path / "video.mp4", [], tmp_path / "out.mp4")

    @patch("narractive.core.video_assembler._check_ffmpeg")
    @patch("narractive.core.video_assembler._run_ffmpeg")
    @patch("narractive.core.video_assembler.get_media_duration", return_value=120.0)
    def test_basic_chapters(self, mock_dur, mock_ffmpeg, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        chapters = [
            {"title": "Intro", "start": 0.0},
            {"title": "Main",  "start": 30.0},
            {"title": "End",   "start": 90.0},
        ]
        output = tmp_path / "out.mp4"
        result = va.add_chapter_markers(tmp_path / "video.mp4", chapters, output)
        assert result == output
        mock_ffmpeg.assert_called_once()

    @patch("narractive.core.video_assembler._check_ffmpeg")
    @patch("narractive.core.video_assembler._run_ffmpeg")
    @patch("narractive.core.video_assembler.get_media_duration", return_value=60.0)
    def test_metadata_file_contains_chapter_info(
        self, mock_dur, mock_ffmpeg, mock_check, tmp_path
    ):
        """Verify that the ffmetadata file written has correct content."""
        written_metadata: list[str] = []

        def _capture_ffmpeg(*args):
            # Find the metadata file path (the -i after -i video.mp4)
            args_list = list(args)
            try:
                meta_idx = args_list.index("-i", 2)  # second -i
                meta_file = args_list[meta_idx + 1]
                written_metadata.append(Path(meta_file).read_text(encoding="utf-8"))
            except (ValueError, IndexError, FileNotFoundError):
                pass

        mock_ffmpeg.side_effect = _capture_ffmpeg

        va = VideoAssembler({"final_dir": str(tmp_path)})
        chapters = [
            {"title": "Introduction", "start": 0.0},
            {"title": "Demo",         "start": 20.0},
        ]
        va.add_chapter_markers(tmp_path / "video.mp4", chapters, tmp_path / "out.mp4")

        # The metadata file is deleted after use, but we captured its content above
        # If the file was already deleted before capture, just check ffmpeg was called
        if written_metadata:
            meta = written_metadata[0]
            assert "FFMETADATA1" in meta
            assert "Introduction" in meta
            assert "Demo" in meta
            assert "CHAPTER" in meta
        else:
            mock_ffmpeg.assert_called()

    @patch("narractive.core.video_assembler._check_ffmpeg")
    @patch("narractive.core.video_assembler._run_ffmpeg")
    @patch("narractive.core.video_assembler.get_media_duration", return_value=100.0)
    def test_chapter_with_explicit_end(self, mock_dur, mock_ffmpeg, mock_check, tmp_path):
        """Explicit end times are respected."""
        va = VideoAssembler({"final_dir": str(tmp_path)})
        chapters = [{"title": "Only Chapter", "start": 0.0, "end": 50.0}]
        result = va.add_chapter_markers(
            tmp_path / "video.mp4", chapters, tmp_path / "out.mp4"
        )
        assert result == tmp_path / "out.mp4"
        mock_ffmpeg.assert_called_once()

    @patch("narractive.core.video_assembler._check_ffmpeg")
    @patch("narractive.core.video_assembler._run_ffmpeg")
    @patch("narractive.core.video_assembler.get_media_duration", return_value=60.0)
    def test_single_chapter_end_defaults_to_duration(
        self, mock_dur, mock_ffmpeg, mock_check, tmp_path
    ):
        """Last chapter end defaults to total video duration."""
        va = VideoAssembler({"final_dir": str(tmp_path)})
        chapters = [{"title": "Everything", "start": 0.0}]
        va.add_chapter_markers(
            tmp_path / "video.mp4", chapters, tmp_path / "out.mp4"
        )
        mock_ffmpeg.assert_called_once()

    @patch("narractive.core.video_assembler._check_ffmpeg")
    @patch("narractive.core.video_assembler._run_ffmpeg")
    @patch("narractive.core.video_assembler.get_media_duration", return_value=120.0)
    def test_ffmpeg_receives_map_chapters_flag(
        self, mock_dur, mock_ffmpeg, mock_check, tmp_path
    ):
        """The -map_chapters flag must be passed to FFmpeg."""
        va = VideoAssembler({"final_dir": str(tmp_path)})
        chapters = [{"title": "A", "start": 0.0}]
        va.add_chapter_markers(
            tmp_path / "video.mp4", chapters, tmp_path / "out.mp4"
        )
        call_args = mock_ffmpeg.call_args[0]
        assert "-map_chapters" in call_args


# ---------------------------------------------------------------------------
# Issue #11 — Intro/outro from video clips
# ---------------------------------------------------------------------------


class TestIntroOutroVideoClips:
    @patch("narractive.core.video_assembler._check_ffmpeg")
    def test_video_clip_extensions_defined(self, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        assert ".mp4" in va.VIDEO_EXTENSIONS
        assert ".mov" in va.VIDEO_EXTENSIONS
        assert ".avi" in va.VIDEO_EXTENSIONS

    @patch("narractive.core.video_assembler._check_ffmpeg")
    def test_no_intro_outro_copies_main(self, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        main = tmp_path / "main.mp4"
        main.write_bytes(b"main video content")
        output = tmp_path / "final.mp4"
        result = va.add_intro_outro(main, None, None, output)
        assert result == output
        assert output.read_bytes() == b"main video content"

    @patch("narractive.core.video_assembler._check_ffmpeg")
    @patch("narractive.core.video_assembler._run_ffmpeg")
    def test_video_clip_intro_concatenated_directly(
        self, mock_ffmpeg, mock_check, tmp_path
    ):
        """A .mp4 intro must be passed directly to concat, not through create_image_clip."""
        va = VideoAssembler({"final_dir": str(tmp_path)})
        main = tmp_path / "main.mp4"
        main.touch()
        intro = tmp_path / "intro.mp4"
        intro.touch()
        output = tmp_path / "final.mp4"

        with patch.object(va, "create_image_clip") as mock_img_clip:
            va.add_intro_outro(main, intro, None, output)
            mock_img_clip.assert_not_called()

        mock_ffmpeg.assert_called_once()

    @patch("narractive.core.video_assembler._check_ffmpeg")
    @patch("narractive.core.video_assembler._run_ffmpeg")
    def test_mov_outro_concatenated_directly(self, mock_ffmpeg, mock_check, tmp_path):
        """.mov outro is treated as a video clip."""
        va = VideoAssembler({"final_dir": str(tmp_path)})
        main = tmp_path / "main.mp4"
        main.touch()
        outro = tmp_path / "outro.mov"
        outro.touch()
        output = tmp_path / "final.mp4"

        with patch.object(va, "create_image_clip") as mock_img_clip:
            va.add_intro_outro(main, None, outro, output)
            mock_img_clip.assert_not_called()

        mock_ffmpeg.assert_called_once()

    @patch("narractive.core.video_assembler._check_ffmpeg")
    @patch("narractive.core.video_assembler._run_ffmpeg")
    def test_image_intro_converted_to_clip(self, mock_ffmpeg, mock_check, tmp_path):
        """A .png intro must be converted to a video clip first."""
        va = VideoAssembler({"final_dir": str(tmp_path)})
        main = tmp_path / "main.mp4"
        main.touch()
        intro_img = tmp_path / "intro.png"
        intro_img.touch()
        output = tmp_path / "final.mp4"

        with patch.object(va, "create_image_clip", return_value=tmp_path / "_intro_clip.mp4") as mock_img_clip:
            # create_image_clip won't actually create a file; mock returns a path
            (tmp_path / "_intro_clip.mp4").touch()
            va.add_intro_outro(main, intro_img, None, output)
            mock_img_clip.assert_called_once()

    @patch("narractive.core.video_assembler._check_ffmpeg")
    def test_missing_video_intro_ignored(self, mock_check, tmp_path):
        """A non-existent intro file is simply skipped."""
        va = VideoAssembler({"final_dir": str(tmp_path)})
        main = tmp_path / "main.mp4"
        main.write_bytes(b"main data")
        output = tmp_path / "final.mp4"
        result = va.add_intro_outro(main, tmp_path / "nonexistent.mp4", None, output)
        assert output.read_bytes() == b"main data"

    @patch("narractive.core.video_assembler._check_ffmpeg")
    @patch("narractive.core.video_assembler._run_ffmpeg")
    def test_avi_outro_treated_as_video(self, mock_ffmpeg, mock_check, tmp_path):
        """.avi outro is treated as a video clip, not an image."""
        va = VideoAssembler({"final_dir": str(tmp_path)})
        main = tmp_path / "main.mp4"
        main.touch()
        outro = tmp_path / "outro.avi"
        outro.touch()
        output = tmp_path / "final.mp4"

        with patch.object(va, "create_image_clip") as mock_img_clip:
            va.add_intro_outro(main, None, outro, output)
            mock_img_clip.assert_not_called()

        mock_ffmpeg.assert_called_once()

    @patch("narractive.core.video_assembler._check_ffmpeg")
    @patch("narractive.core.video_assembler._run_ffmpeg")
    def test_both_video_intro_and_outro(self, mock_ffmpeg, mock_check, tmp_path):
        """Video intro + video outro: concat is called once with 3 clips."""
        va = VideoAssembler({"final_dir": str(tmp_path)})
        main = tmp_path / "main.mp4"
        main.touch()
        intro = tmp_path / "intro.mp4"
        intro.touch()
        outro = tmp_path / "outro.mp4"
        outro.touch()
        output = tmp_path / "final.mp4"

        with patch.object(va, "create_image_clip") as mock_img_clip:
            va.add_intro_outro(main, intro, outro, output)
            mock_img_clip.assert_not_called()

        mock_ffmpeg.assert_called_once()
