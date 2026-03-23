"""Tests for `narractive init` command using Click's test runner."""
from __future__ import annotations

import pytest
from click.testing import CliRunner

from video_automation.cli import cli

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCLIInit:
    def test_init_no_interactive_creates_structure(self, runner, tmp_path):
        """--no-interactive scaffolds the full directory structure without prompts."""
        project_dir = tmp_path / "my_demo"
        result = runner.invoke(cli, ["init", str(project_dir), "--no-interactive"])

        assert result.exit_code == 0, f"CLI exited non-zero: {result.output}"

        # Required files
        assert (project_dir / "config.yaml").exists(), "config.yaml missing"
        assert (project_dir / "sequences" / "__init__.py").exists()
        assert (project_dir / "sequences" / "seq00_intro.py").exists()
        assert (project_dir / "narrations").is_dir()
        assert (project_dir / "diagrams" / "definitions.py").exists()

    def test_init_no_interactive_default_language_fr(self, runner, tmp_path):
        """Default language is 'fr' with --no-interactive."""
        project_dir = tmp_path / "proj"
        result = runner.invoke(cli, ["init", str(project_dir), "--no-interactive"])
        assert result.exit_code == 0
        assert (project_dir / "narrations" / "fr.yaml").exists()

    def test_init_no_interactive_config_yaml_content(self, runner, tmp_path):
        """Generated config.yaml contains expected keys."""
        import yaml

        project_dir = tmp_path / "myapp"
        runner.invoke(cli, ["init", str(project_dir), "--no-interactive"])

        config_path = project_dir / "config.yaml"
        assert config_path.exists()
        cfg = yaml.safe_load(config_path.read_text())
        assert "obs" in cfg
        assert "narration" in cfg
        assert "languages" in cfg

    def test_init_no_interactive_sequences_init_content(self, runner, tmp_path):
        """sequences/__init__.py imports Seq00Intro and exports SEQUENCES."""
        project_dir = tmp_path / "myapp"
        runner.invoke(cli, ["init", str(project_dir), "--no-interactive"])

        init_content = (project_dir / "sequences" / "__init__.py").read_text()
        assert "Seq00Intro" in init_content
        assert "SEQUENCES" in init_content

    def test_init_no_interactive_seq00_intro_content(self, runner, tmp_path):
        """sequences/seq00_intro.py defines Seq00Intro with required attributes."""
        project_dir = tmp_path / "myapp"
        runner.invoke(cli, ["init", str(project_dir), "--no-interactive"])

        seq_content = (project_dir / "sequences" / "seq00_intro.py").read_text()
        assert "class Seq00Intro" in seq_content
        assert "sequence_id" in seq_content
        assert "def run" in seq_content

    def test_init_no_interactive_prints_next_steps(self, runner, tmp_path):
        """Output includes 'Next steps' summary."""
        project_dir = tmp_path / "myapp"
        result = runner.invoke(cli, ["init", str(project_dir), "--no-interactive"])
        assert "Next steps" in result.output or "next" in result.output.lower()

    def test_init_no_interactive_idempotent(self, runner, tmp_path):
        """Running init twice doesn't crash (directory already exists)."""
        project_dir = tmp_path / "myapp"
        r1 = runner.invoke(cli, ["init", str(project_dir), "--no-interactive"])
        r2 = runner.invoke(cli, ["init", str(project_dir), "--no-interactive"])
        assert r1.exit_code == 0
        assert r2.exit_code == 0

    def test_init_does_not_require_config_yaml(self, runner, tmp_path):
        """init subcommand works even when no config.yaml exists in cwd."""
        project_dir = tmp_path / "new_project"
        # Run from tmp_path which has no config.yaml
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["init", str(project_dir), "--no-interactive"])
        assert result.exit_code == 0

    def test_init_diagrams_definitions_py(self, runner, tmp_path):
        """diagrams/definitions.py is created with DIAGRAMS list."""
        project_dir = tmp_path / "myapp"
        runner.invoke(cli, ["init", str(project_dir), "--no-interactive"])

        diag_content = (project_dir / "diagrams" / "definitions.py").read_text()
        assert "DIAGRAMS" in diag_content
