"""Tests for FrameCapturer — headless screen capture for Docker/Xvfb."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from narractive.core.frame_capturer import FrameCapturer


# ---------------------------------------------------------------------------
# Init and config
# ---------------------------------------------------------------------------


class TestFrameCapturerInit:
    def test_defaults(self):
        fc = FrameCapturer({})
        assert fc.fps == 10
        assert fc.resolution == "1920x1080"
        assert fc.quality == 23
        assert fc.codec == "libx264"
        assert fc.format == "mp4"
        assert fc.capture_method == "xdotool"

    def test_custom_config(self, tmp_path):
        fc = FrameCapturer({
            "fps": 30,
            "output_dir": str(tmp_path / "out"),
            "resolution": "2560x1440",
            "display": ":1",
            "quality": 18,
            "codec": "libx265",
            "format": "mkv",
            "method": "scrot",
            "scenes": {"main": "Main"},
        })
        assert fc.fps == 30
        assert fc.resolution == "2560x1440"
        assert fc.display == ":1"
        assert fc.quality == 18
        assert fc.codec == "libx265"
        assert fc.format == "mkv"
        assert fc.capture_method == "scrot"
        assert fc.scenes == {"main": "Main"}

    def test_initial_state(self):
        fc = FrameCapturer({})
        assert fc._recording is False
        assert fc._paused is False
        assert fc._frame_count == 0
        assert fc._current_scene == "default"


# ---------------------------------------------------------------------------
# Scene management (compatibility stubs)
# ---------------------------------------------------------------------------


class TestFrameCapturerScenes:
    def test_switch_scene(self):
        fc = FrameCapturer({})
        fc.switch_scene("Diagram")
        assert fc._current_scene == "Diagram"

    def test_get_current_scene(self):
        fc = FrameCapturer({})
        assert fc.get_current_scene() == "default"
        fc.switch_scene("Test")
        assert fc.get_current_scene() == "Test"

    def test_list_scenes_with_config(self):
        fc = FrameCapturer({"scenes": {"main": "Main", "intro": "Intro"}})
        scenes = fc.list_scenes()
        assert "Main" in scenes
        assert "Intro" in scenes

    def test_list_scenes_empty(self):
        fc = FrameCapturer({})
        assert fc.list_scenes() == ["default"]


# ---------------------------------------------------------------------------
# Source visibility (no-op compatibility)
# ---------------------------------------------------------------------------


class TestFrameCapturerSourceVisibility:
    def test_set_source_visibility_noop(self):
        fc = FrameCapturer({})
        # Should not raise
        fc.set_source_visibility("scene", "source", True)
        fc.set_source_visibility("scene", "source", False)


# ---------------------------------------------------------------------------
# Recording status
# ---------------------------------------------------------------------------


class TestFrameCapturerRecordingStatus:
    def test_status_not_recording(self):
        fc = FrameCapturer({})
        status = fc.get_recording_status()
        assert status["active"] is False
        assert status["paused"] is False
        assert status["frames"] == 0

    def test_status_timecode_format(self):
        fc = FrameCapturer({})
        fc._recording = True
        fc._start_time = 0  # epoch start
        import time
        fc._start_time = time.time() - 65  # 1 min 5 sec ago
        status = fc.get_recording_status()
        assert ":" in status["timecode"]


# ---------------------------------------------------------------------------
# Diagram overlay compatibility
# ---------------------------------------------------------------------------


class TestFrameCapturerDiagramOverlay:
    def test_show_diagram_overlay_true(self):
        fc = FrameCapturer({"scenes": {"diagram_overlay": "Diag"}})
        fc.show_diagram_overlay(visible=True)
        assert fc._current_scene == "Diag"

    def test_show_diagram_overlay_false(self):
        fc = FrameCapturer({"scenes": {"main": "Main"}})
        fc.show_diagram_overlay(visible=False)
        assert fc._current_scene == "Main"


# ---------------------------------------------------------------------------
# Transition helpers
# ---------------------------------------------------------------------------


class TestFrameCapturerTransitions:
    def setup_method(self):
        self.fc = FrameCapturer({"scenes": {
            "main": "Main",
            "intro_scene": "Intro",
            "outro_scene": "Outro",
        }})

    def test_transition_to_main(self):
        self.fc.transition_to_main()
        assert self.fc._current_scene == "Main"

    def test_transition_to_qgis_is_alias(self):
        assert FrameCapturer.transition_to_qgis is FrameCapturer.transition_to_main

    def test_transition_to_intro(self):
        self.fc.transition_to_intro()
        assert self.fc._current_scene == "Intro"

    def test_transition_to_outro(self):
        self.fc.transition_to_outro()
        assert self.fc._current_scene == "Outro"


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestFrameCapturerContextManager:
    @patch.object(FrameCapturer, "connect")
    @patch.object(FrameCapturer, "disconnect")
    def test_context_manager(self, mock_disconnect, mock_connect):
        fc = FrameCapturer({})
        with fc as f:
            mock_connect.assert_called_once()
            assert f is fc
        mock_disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# Recording lifecycle
# ---------------------------------------------------------------------------


class TestFrameCapturerRecording:
    def test_start_recording_sets_state(self):
        fc = FrameCapturer({"output_dir": "/tmp/test_cap"})
        with patch.object(fc, "_capture_loop"):
            fc._thread = MagicMock()
            fc._recording = True
            assert fc._recording is True

    def test_stop_recording_not_recording(self):
        fc = FrameCapturer({})
        result = fc.stop_recording()
        assert result is None

    def test_pause_resume(self):
        fc = FrameCapturer({})
        fc.pause_recording()
        assert fc._paused is True
        fc.resume_recording()
        assert fc._paused is False


# ---------------------------------------------------------------------------
# Frame assembly
# ---------------------------------------------------------------------------


class TestFrameCapturerAssembly:
    @patch("subprocess.run")
    def test_assemble_frames_no_frames(self, mock_run, tmp_path):
        fc = FrameCapturer({"output_dir": str(tmp_path)})
        frames_dir = tmp_path / "empty_frames"
        frames_dir.mkdir()
        result = fc.assemble_frames(str(frames_dir), str(tmp_path / "out.mp4"))
        assert result is None
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_assemble_frames_success(self, mock_run, tmp_path):
        fc = FrameCapturer({"output_dir": str(tmp_path)})
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        # Create dummy frames
        for i in range(5):
            (frames_dir / f"frame_{i:06d}.png").touch()
        output = tmp_path / "out.mp4"
        output.touch()  # Simulate ffmpeg creating the file
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = fc.assemble_frames(str(frames_dir), str(output), fps=10)
        assert result is not None
        mock_run.assert_called_once()

    @patch("subprocess.run", side_effect=__import__("subprocess").CalledProcessError(1, "ffmpeg"))
    def test_assemble_frames_ffmpeg_error(self, mock_run, tmp_path):
        fc = FrameCapturer({"output_dir": str(tmp_path)})
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        (frames_dir / "frame_000000.png").touch()
        result = fc.assemble_frames(str(frames_dir), str(tmp_path / "out.mp4"))
        assert result is None

    @patch("subprocess.run")
    def test_assemble_with_audio(self, mock_run, tmp_path):
        fc = FrameCapturer({"output_dir": str(tmp_path)})
        mock_run.return_value = MagicMock(returncode=0)
        result = fc.assemble_with_audio(
            str(tmp_path / "video.mp4"),
            str(tmp_path / "audio.mp3"),
            str(tmp_path / "output.mp4"),
        )
        assert result is not None
        mock_run.assert_called_once()

    def test_cleanup_frames(self, tmp_path):
        fc = FrameCapturer({})
        frames_dir = tmp_path / "frames_to_clean"
        frames_dir.mkdir()
        (frames_dir / "frame_000000.png").touch()
        fc.cleanup_frames(str(frames_dir))
        assert not frames_dir.exists()

    def test_cleanup_frames_nonexistent(self, tmp_path):
        fc = FrameCapturer({})
        # Should not raise
        fc.cleanup_frames(str(tmp_path / "nonexistent"))


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------


class TestFrameCapturerScreenshot:
    @patch.object(FrameCapturer, "_capture_frame")
    def test_take_screenshot(self, mock_capture, tmp_path):
        fc = FrameCapturer({"output_dir": str(tmp_path)})
        result = fc.take_screenshot(file_path=str(tmp_path / "shot.png"))
        assert result == str(tmp_path / "shot.png")
        mock_capture.assert_called_once()

    @patch.object(FrameCapturer, "_capture_frame")
    def test_take_screenshot_auto_path(self, mock_capture, tmp_path):
        fc = FrameCapturer({"output_dir": str(tmp_path)})
        result = fc.take_screenshot()
        assert "screenshot_" in result
        assert result.endswith(".png")
