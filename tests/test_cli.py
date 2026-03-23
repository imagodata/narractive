"""Tests for the CLI module — config loading, sequence loading, command dispatch."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from video_automation.cli import load_config, load_sequences_from_package


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_valid_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"narration": {"engine": "edge-tts"}}))
        cfg = load_config(config_file)
        assert cfg["narration"]["engine"] == "edge-tts"

    def test_missing_config_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            load_config(tmp_path / "nonexistent.yaml")

    def test_empty_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        cfg = load_config(config_file)
        assert cfg is None


# ---------------------------------------------------------------------------
# Sequence loading
# ---------------------------------------------------------------------------


class TestLoadSequencesFromPackage:
    def test_invalid_package_raises(self):
        with pytest.raises((ImportError, ModuleNotFoundError)):
            load_sequences_from_package("nonexistent.package.path")


# ---------------------------------------------------------------------------
# CLI dispatch (click integration)
# ---------------------------------------------------------------------------


class TestCLIDispatch:
    @pytest.fixture
    def config_file(self, tmp_path):
        cfg = {
            "narration": {"engine": "edge-tts", "output_dir": str(tmp_path / "narr")},
            "diagrams": {"output_dir": str(tmp_path / "diag")},
            "output": {"final_dir": str(tmp_path / "final")},
            "obs": {},
            "capture": {},
            "subtitles": {"enabled": True},
            "timing": {"transition_pause": 0.0},
            "app": {"window_title": "Test"},
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(cfg))
        return config_path

    def test_cli_no_args_shows_help(self, config_file):
        from click.testing import CliRunner
        from video_automation.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["--config", str(config_file)])
        assert result.exit_code == 0

    def test_cli_list_without_package(self, config_file):
        from click.testing import CliRunner
        from video_automation.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["--config", str(config_file), "--list"])
        # Should fail because no --sequences-package
        assert result.exit_code != 0 or "No --sequences-package" in (result.output or "")

    def test_cli_diagrams_without_module(self, config_file):
        from click.testing import CliRunner
        from video_automation.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["--config", str(config_file), "--diagrams"])
        assert result.exit_code != 0 or "No --diagrams-module" in (result.output or "")

    def test_cli_dry_run_flag(self, config_file):
        from click.testing import CliRunner
        from video_automation.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--config", str(config_file),
            "--calibrate", "--dry-run",
        ])
        assert "DRY-RUN" in (result.output or "")

    def test_cli_verbose_flag(self, config_file):
        from click.testing import CliRunner
        from video_automation.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--config", str(config_file),
            "--verbose",
        ])
        # Should run without error
        assert result.exit_code == 0

    def test_cli_narration_dry_run(self, config_file, tmp_path):
        from click.testing import CliRunner
        from video_automation.cli import cli
        # Create a narrations.yaml
        narr_file = tmp_path / "narrations.yaml"
        narr_file.write_text(yaml.dump({"original": {"seq01": "Hello"}}))
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--config", str(config_file),
            "--narration", "--dry-run",
            "--narrations-file", str(narr_file),
        ])
        assert "DRY-RUN" in (result.output or "")

    def test_cli_subtitles_no_narrations_dir(self, config_file, tmp_path):
        from click.testing import CliRunner
        from video_automation.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--config", str(config_file),
            "--subtitles",
            "--narrations-dir", str(tmp_path / "nonexistent"),
        ])
        # Should handle gracefully (the dir doesn't exist check happens via click)
        # This will fail at click parameter validation since exists=True
        assert result.exit_code != 0 or "not found" in (result.output or "").lower()

    def test_cli_assemble_dry_run(self, config_file):
        from click.testing import CliRunner
        from video_automation.cli import cli
        with patch("video_automation.core.video_assembler._check_ffmpeg"):
            runner = CliRunner()
            result = runner.invoke(cli, [
                "--config", str(config_file),
                "--assemble", "--dry-run",
            ])
            assert "DRY-RUN" in (result.output or "")

    def test_cli_sequence_out_of_range(self, config_file):
        from click.testing import CliRunner
        from video_automation.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--config", str(config_file),
            "--sequence", "999",
            "--sequences-package", "examples.filtermate.sequences",
        ])
        # Should report out of range or exit non-zero
        assert result.exit_code != 0 or "out of range" in (result.output or "")
