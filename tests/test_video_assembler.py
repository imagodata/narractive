"""Tests for VideoAssembler (config parsing, FFmpeg checks)."""

from __future__ import annotations

from unittest.mock import patch

from video_automation.core.video_assembler import VideoAssembler


class TestVideoAssembler:
    @patch("video_automation.core.video_assembler._check_ffmpeg")
    def test_init_defaults(self, mock_check, tmp_path):
        va = VideoAssembler({"final_dir": str(tmp_path / "final")})
        assert va.resolution == "1920x1080"
        assert va.fps == 30
        assert va.codec == "libx264"
        assert va.quality == "23"
        assert (tmp_path / "final").is_dir()

    @patch("video_automation.core.video_assembler._check_ffmpeg")
    def test_init_custom_config(self, mock_check, tmp_path):
        va = VideoAssembler(
            {
                "final_dir": str(tmp_path / "out"),
                "resolution": "2560x1440",
                "fps": 60,
                "codec": "libx265",
                "quality": 18,
            }
        )
        assert va.resolution == "2560x1440"
        assert va.fps == 60
        assert va.codec == "libx265"
        assert va.quality == "18"
