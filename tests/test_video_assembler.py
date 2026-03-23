"""Tests for VideoAssembler — FFmpeg post-production pipeline."""
from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_automation.core.video_assembler import (
    QUALITY_PRESETS,
    VideoAssembler,
    _check_ffmpeg,
    _run_ffmpeg,
    format_duration,
    get_media_duration,
)


# ---------------------------------------------------------------------------
# Module-level utilities
# ---------------------------------------------------------------------------


class TestCheckFfmpeg:
    @patch("shutil.which", return_value=None)
    def test_raises_when_missing(self, mock_which):
        with pytest.raises(RuntimeError, match="FFmpeg not found"):
            _check_ffmpeg()

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    def test_passes_when_present(self, mock_which):
        _check_ffmpeg()  # should not raise


class TestRunFfmpeg:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = _run_ffmpeg("-version")
        assert result.returncode == 0

    @patch("subprocess.run")
    def test_failure_raises(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
        with pytest.raises(Exception):
            _run_ffmpeg("-invalid")

    @patch("subprocess.run")
    def test_failure_no_check(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        result = _run_ffmpeg("-invalid", check=False)
        assert result.returncode == 1


class TestFormatDuration:
    def test_seconds_only(self):
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self):
        assert format_duration(125) == "2m05s"

    def test_zero(self):
        assert format_duration(0) == "0s"

    def test_exact_minute(self):
        assert format_duration(60) == "1m00s"


class TestGetMediaDuration:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        import json
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"format": {"duration": "45.5"}}),
        )
        dur = get_media_duration("test.mp4")
        assert dur == 45.5

    @patch("subprocess.run")
    def test_ffprobe_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        dur = get_media_duration("test.mp4")
        assert dur is None

    @patch("subprocess.run", side_effect=FileNotFoundError("no ffprobe"))
    def test_ffprobe_not_found(self, mock_run):
        dur = get_media_duration("test.mp4")
        assert dur is None

    @patch("subprocess.run")
    def test_no_duration_in_response(self, mock_run):
        import json
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"format": {}}),
        )
        dur = get_media_duration("test.mp4")
        assert dur is None


class TestQualityPresets:
    def test_draft_exists(self):
        assert "draft" in QUALITY_PRESETS
        assert QUALITY_PRESETS["draft"]["preset"] == "ultrafast"

    def test_final_exists(self):
        assert "final" in QUALITY_PRESETS
        assert QUALITY_PRESETS["final"]["preset"] == "slow"
        assert QUALITY_PRESETS["final"]["crf"] < QUALITY_PRESETS["draft"]["crf"]


# ---------------------------------------------------------------------------
# VideoAssembler init
# ---------------------------------------------------------------------------


class TestVideoAssemblerInit:
    @patch("video_automation.core.video_assembler._check_ffmpeg")
    def test_defaults(self, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path / "final")})
        assert va.resolution == "1920x1080"
        assert va.fps == 30
        assert va.codec == "libx264"
        assert va.quality == "23"
        assert (tmp_path / "final").is_dir()

    @patch("video_automation.core.video_assembler._check_ffmpeg")
    def test_custom_config(self, mock_check, tmp_path):
        va = VideoAssembler({
            "final_dir": str(tmp_path / "out"),
            "resolution": "2560x1440",
            "fps": 60,
            "codec": "libx265",
            "quality": 18,
        })
        assert va.resolution == "2560x1440"
        assert va.fps == 60
        assert va.codec == "libx265"
        assert va.quality == "18"


# ---------------------------------------------------------------------------
# Remux
# ---------------------------------------------------------------------------


class TestVideoAssemblerRemux:
    @patch("video_automation.core.video_assembler._check_ffmpeg")
    @patch("video_automation.core.video_assembler._run_ffmpeg")
    def test_remux_default_path(self, mock_ffmpeg, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        result = va.remux_mkv_to_mp4(tmp_path / "video.mkv")
        assert result == tmp_path / "video.mp4"
        mock_ffmpeg.assert_called_once()

    @patch("video_automation.core.video_assembler._check_ffmpeg")
    @patch("video_automation.core.video_assembler._run_ffmpeg")
    def test_remux_custom_path(self, mock_ffmpeg, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        result = va.remux_mkv_to_mp4(tmp_path / "video.mkv", tmp_path / "custom.mp4")
        assert result == tmp_path / "custom.mp4"


# ---------------------------------------------------------------------------
# Diagram overlay
# ---------------------------------------------------------------------------


class TestVideoAssemblerDiagramOverlay:
    @patch("video_automation.core.video_assembler._check_ffmpeg")
    @patch("video_automation.core.video_assembler._run_ffmpeg")
    def test_no_diagrams_copies_source(self, mock_ffmpeg, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake video")
        output = tmp_path / "output.mp4"
        result = va.combine_recording_with_diagrams(source, [], [], output)
        assert result == output
        assert output.read_bytes() == b"fake video"
        mock_ffmpeg.assert_not_called()

    @patch("video_automation.core.video_assembler._check_ffmpeg")
    def test_mismatched_lengths_raises(self, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        with pytest.raises(ValueError, match="same length"):
            va.combine_recording_with_diagrams(
                tmp_path / "source.mp4",
                ["diag1.png", "diag2.png"],
                [5.0],  # only one timestamp for two diagrams
                tmp_path / "output.mp4",
            )


# ---------------------------------------------------------------------------
# Intro/Outro concatenation
# ---------------------------------------------------------------------------


class TestVideoAssemblerIntroOutro:
    @patch("video_automation.core.video_assembler._check_ffmpeg")
    def test_single_clip_copies(self, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        video = tmp_path / "main.mp4"
        video.write_bytes(b"main video")
        output = tmp_path / "final.mp4"
        result = va.add_intro_outro(video, None, None, output)
        assert result == output
        assert output.read_bytes() == b"main video"

    @patch("video_automation.core.video_assembler._check_ffmpeg")
    @patch("video_automation.core.video_assembler._run_ffmpeg")
    def test_with_intro_and_outro(self, mock_ffmpeg, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        video = tmp_path / "main.mp4"
        video.touch()
        intro = tmp_path / "intro.mp4"
        intro.touch()
        outro = tmp_path / "outro.mp4"
        outro.touch()
        output = tmp_path / "final.mp4"
        va.add_intro_outro(video, intro, outro, output)
        mock_ffmpeg.assert_called_once()

    @patch("video_automation.core.video_assembler._check_ffmpeg")
    def test_missing_intro_ignored(self, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        video = tmp_path / "main.mp4"
        video.write_bytes(b"video data")
        output = tmp_path / "final.mp4"
        result = va.add_intro_outro(video, tmp_path / "missing_intro.mp4", None, output)
        # Should just copy main video
        assert output.read_bytes() == b"video data"


# ---------------------------------------------------------------------------
# assemble_sequence
# ---------------------------------------------------------------------------


class TestVideoAssemblerAssembleSequence:
    @patch("video_automation.core.video_assembler._check_ffmpeg")
    def test_missing_recording(self, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        config = {
            "obs": {}, "narration": {}, "subtitles": {},
            "output": {}, "capture": {},
        }
        result = va.assemble_sequence("seq01", "fr", tmp_path, config)
        assert result is None

    @patch("video_automation.core.video_assembler._check_ffmpeg")
    def test_dry_run(self, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path)})
        # Create required files
        rec_dir = tmp_path / "output" / "fr" / "recordings"
        narr_dir = tmp_path / "output" / "fr" / "narrations"
        rec_dir.mkdir(parents=True)
        narr_dir.mkdir(parents=True)
        (rec_dir / "seq01.mp4").touch()
        (narr_dir / "seq01.wav").touch()
        config = {
            "obs": {"output_dir": str(rec_dir)},
            "narration": {"output_dir": str(narr_dir)},
            "subtitles": {},
            "output": {"final_dir": str(tmp_path / "output" / "fr" / "final")},
            "capture": {},
        }
        with patch("video_automation.core.video_assembler.get_media_duration", return_value=10.0):
            result = va.assemble_sequence("seq01", "fr", tmp_path, config, dry_run=True)
        assert result is not None
