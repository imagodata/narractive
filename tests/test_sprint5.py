"""Sprint 5 — Unit tests for:
  - Issue #12: Pipeline state persistence (resume interrupted runs)
  - Issue #13: Plugin architecture for custom TTS engines
  - Issue #14: Production summary / report command
"""
from __future__ import annotations

import json
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# Issue #12 — Pipeline state persistence
# ===========================================================================

from narractive.core.pipeline_state import (
    PipelineState,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    DEFAULT_STATE_FILE,
)


class TestPipelineStateBasics:
    def test_default_state_is_empty(self, tmp_path):
        state = PipelineState(tmp_path / "state.json")
        assert state._data == {}

    def test_load_missing_file_returns_empty(self, tmp_path):
        state = PipelineState.load(tmp_path / "nonexistent.json")
        assert state._data == {}

    def test_start_run_sets_fields(self, tmp_path):
        state = PipelineState(tmp_path / "state.json")
        state.start_run(sequences_package="my.pkg", total=5)
        assert state._data["sequences_package"] == "my.pkg"
        assert state._data["total"] == 5
        assert "run_id" in state._data

    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "state.json"
        state = PipelineState(path)
        state.start_run(sequences_package="test.pkg", total=3)
        state.mark_completed("seq00", recording_path="output/seq00.mkv")
        state.save()

        loaded = PipelineState.load(path)
        assert loaded.is_completed("seq00")
        assert "seq00" in loaded.get_recordings()

    def test_mark_running(self, tmp_path):
        state = PipelineState(tmp_path / "s.json")
        state.start_run()
        state.mark_running("seq01")
        assert state._data["sequences"]["seq01"]["status"] == STATUS_RUNNING

    def test_mark_failed_with_error(self, tmp_path):
        state = PipelineState(tmp_path / "s.json")
        state.start_run()
        state.mark_failed("seq02", error="TimeoutError: OBS")
        assert "seq02" in state.failed_ids()
        assert "TimeoutError" in state._data["sequences"]["seq02"]["error"]

    def test_completed_ids(self, tmp_path):
        state = PipelineState(tmp_path / "s.json")
        state.start_run()
        state.mark_completed("seq00")
        state.mark_completed("seq02")
        state.mark_failed("seq01")
        assert state.completed_ids() == ["seq00", "seq02"]

    def test_failed_ids(self, tmp_path):
        state = PipelineState(tmp_path / "s.json")
        state.start_run()
        state.mark_failed("seq01")
        assert state.failed_ids() == ["seq01"]

    def test_pending_ids(self, tmp_path):
        state = PipelineState(tmp_path / "s.json")
        state.start_run()
        state.mark_completed("seq00")
        all_ids = ["seq00", "seq01", "seq02"]
        pending = state.pending_ids(all_ids)
        assert pending == ["seq01", "seq02"]

    def test_resume_from_index_skips_completed(self, tmp_path):
        state = PipelineState(tmp_path / "s.json")
        state.start_run()
        state.mark_completed("seq00")
        state.mark_completed("seq01")
        all_ids = ["seq00", "seq01", "seq02", "seq03"]
        assert state.resume_from_index(all_ids) == 2

    def test_resume_from_index_all_done(self, tmp_path):
        state = PipelineState(tmp_path / "s.json")
        state.start_run()
        all_ids = ["seq00", "seq01"]
        for sid in all_ids:
            state.mark_completed(sid)
        assert state.resume_from_index(all_ids) == 2

    def test_resume_from_index_empty_state(self, tmp_path):
        state = PipelineState(tmp_path / "s.json")
        all_ids = ["seq00", "seq01"]
        assert state.resume_from_index(all_ids) == 0

    def test_delete_removes_file(self, tmp_path):
        path = tmp_path / "state.json"
        state = PipelineState(path)
        state.start_run()
        state.save()
        assert path.exists()
        state.delete()
        assert not path.exists()
        assert state._data == {}

    def test_from_config_uses_state_file_key(self, tmp_path):
        config = {"output": {"state_file": str(tmp_path / "custom.json")}}
        state = PipelineState.from_config(config)
        assert state.state_file == tmp_path / "custom.json"

    def test_from_config_default(self, tmp_path):
        config = {}
        state = PipelineState.from_config(config)
        assert str(state.state_file) == DEFAULT_STATE_FILE

    def test_status_table_contains_seq_ids(self, tmp_path):
        state = PipelineState(tmp_path / "s.json")
        state.start_run()
        state.mark_completed("seq00")
        state.mark_failed("seq01", error="boom")
        table = state.status_table(["seq00", "seq01", "seq02"])
        assert "seq00" in table
        assert "seq01" in table
        assert "seq02" in table

    def test_to_dict_has_expected_keys(self, tmp_path):
        state = PipelineState(tmp_path / "s.json")
        state.start_run()
        state.mark_completed("seq00")
        all_ids = ["seq00", "seq01"]
        d = state.to_dict(all_ids)
        assert "completed" in d
        assert "failed" in d
        assert "pending" in d
        assert d["completed"] == ["seq00"]
        assert d["pending"] == ["seq01"]

    def test_corrupted_state_file_ignored(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json", encoding="utf-8")
        state = PipelineState.load(path)
        assert state._data == {}

    def test_recordings_stored(self, tmp_path):
        state = PipelineState(tmp_path / "s.json")
        state.start_run()
        state.mark_completed("seq00", recording_path="/out/seq00.mkv")
        recs = state.get_recordings()
        assert recs["seq00"] == "/out/seq00.mkv"


# ===========================================================================
# Issue #13 — Plugin architecture for custom TTS engines
# ===========================================================================

from narractive.core.tts_base import (
    TTSEngine,
    register_tts_engine,
    get_tts_engine,
    list_registered_engines,
    _REGISTRY,
)


class _MockEngine(TTSEngine):
    engine_name = "mock-test-engine-sprint5"

    def generate(self, text: str, output_path: Path, lang: str = "fr", **kwargs) -> Path:
        output_path.write_bytes(b"fake-audio")
        return output_path


class TestTTSEngineRegistry:
    def setup_method(self):
        # Remove our test engine before each test to keep tests isolated
        _REGISTRY.pop("mock-test-engine-sprint5", None)

    def teardown_method(self):
        _REGISTRY.pop("mock-test-engine-sprint5", None)

    def test_register_and_retrieve(self):
        register_tts_engine(_MockEngine)
        assert get_tts_engine("mock-test-engine-sprint5") is _MockEngine

    def test_list_includes_registered(self):
        register_tts_engine(_MockEngine)
        assert "mock-test-engine-sprint5" in list_registered_engines()

    def test_unregistered_engine_returns_none(self):
        assert get_tts_engine("totally-unknown-xyz") is None

    def test_register_without_engine_name_raises(self):
        class BadEngine(TTSEngine):
            engine_name = ""

            def generate(self, text, output_path, lang="fr", **kwargs):
                return output_path

        with pytest.raises(ValueError, match="engine_name"):
            register_tts_engine(BadEngine)

    def test_generate_writes_file(self, tmp_path):
        register_tts_engine(_MockEngine)
        engine = _MockEngine()
        out = tmp_path / "test.mp3"
        result = engine.generate("Hello world", out, lang="en")
        assert result.exists()
        assert result.read_bytes() == b"fake-audio"

    def test_validate_config_default_returns_empty(self):
        register_tts_engine(_MockEngine)
        engine = _MockEngine()
        errors = engine.validate_config({})
        assert errors == []

    def test_get_duration_fallback(self, tmp_path):
        """get_duration returns 0.0 when mutagen is unavailable and file is not audio."""
        engine = _MockEngine()
        fake_path = tmp_path / "fake.mp3"
        fake_path.write_bytes(b"not audio")
        dur = engine.get_duration(fake_path)
        assert isinstance(dur, float)


class TestSilencePluginExample:
    """Test the example custom TTS plugin."""

    def test_silence_engine_generates_wav(self, tmp_path):
        from examples.custom_tts_plugin import SilenceTTSEngine

        engine = SilenceTTSEngine()
        out = tmp_path / "silence.wav"
        result = engine.generate("Hello world test sentence.", out)
        assert result.exists()
        assert result.suffix == ".wav"

    def test_silence_engine_name(self):
        from examples.custom_tts_plugin import SilenceTTSEngine

        assert SilenceTTSEngine.engine_name == "silence"

    def test_silence_engine_validate_config(self):
        from examples.custom_tts_plugin import SilenceTTSEngine

        engine = SilenceTTSEngine()
        assert engine.validate_config({"duration": 1.5}) == []
        errors = engine.validate_config({"duration": -1})
        assert len(errors) > 0

    def test_silence_wav_is_valid(self, tmp_path):
        from examples.custom_tts_plugin import SilenceTTSEngine

        engine = SilenceTTSEngine()
        out = tmp_path / "check.wav"
        result = engine.generate("Five words for test.", out)

        with wave.open(str(result), "r") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getnframes() > 0


class TestNarratorPluginIntegration:
    """Test that Narrator correctly dispatches to registered plugins."""

    def setup_method(self):
        _REGISTRY.pop("mock-test-engine-sprint5", None)

    def teardown_method(self):
        _REGISTRY.pop("mock-test-engine-sprint5", None)

    def test_narrator_uses_registered_plugin(self, tmp_path):
        from narractive.core.narrator import Narrator

        register_tts_engine(_MockEngine)
        narrator = Narrator({"engine": "mock-test-engine-sprint5",
                              "output_dir": str(tmp_path)})
        out = tmp_path / "seq00_narration.mp3"
        result = narrator.generate_narration("Test narration.", out)
        assert result.exists()

    def test_narrator_raises_for_unknown_engine(self, tmp_path):
        from narractive.core.narrator import Narrator

        narrator = Narrator({"engine": "totally-unknown-xyz-engine",
                              "output_dir": str(tmp_path)})
        with pytest.raises(ValueError, match="Unknown TTS engine"):
            narrator.generate_narration("test", tmp_path / "out.mp3")

    def test_register_tts_engine_importable_from_narrator(self):
        from narractive.core.narrator import register_tts_engine as rte
        assert callable(rte)


# ===========================================================================
# Issue #14 — Production summary / report command
# ===========================================================================

from narractive.core.report import (
    ProductionReport,
    SequenceEntry,
    _fmt_duration,
    _fmt_size,
)


class TestFormatHelpers:
    def test_fmt_duration_seconds(self):
        assert _fmt_duration(45.0) == "45s"

    def test_fmt_duration_minutes(self):
        assert _fmt_duration(90.0) == "1m 30s"

    def test_fmt_duration_zero(self):
        assert _fmt_duration(0.0) == "0s"

    def test_fmt_size_bytes(self):
        assert "B" in _fmt_size(512)

    def test_fmt_size_megabytes(self):
        result = _fmt_size(5 * 1024 * 1024)
        assert "MB" in result

    def test_fmt_size_zero(self):
        assert _fmt_size(0) == "0 B"


class TestSequenceEntry:
    def test_to_dict_keys(self):
        entry = SequenceEntry("seq00")
        d = entry.to_dict()
        assert "seq_id" in d
        assert "clip_duration" in d
        assert "narration_duration" in d
        assert "subtitles" in d

    def test_to_dict_with_paths(self, tmp_path):
        entry = SequenceEntry("seq01")
        entry.clip_path = tmp_path / "seq01.mkv"
        entry.clip_duration = 30.5
        d = entry.to_dict()
        assert d["clip_duration"] == 30.5
        assert "seq01.mkv" in d["clip"]


class TestProductionReport:
    def _make_config(self, tmp_path):
        return {
            "output": {
                "final_dir": str(tmp_path / "final"),
                "clips_dir": str(tmp_path / "obs"),
                "state_file": str(tmp_path / ".narractive-state.json"),
            },
            "narration": {
                "engine": "edge-tts",
                "output_dir": str(tmp_path / "narration"),
            },
            "subtitles": {
                "output_dir": str(tmp_path / "{lang}" / "subtitles"),
            },
            "languages": {"fr": {}, "en": {}},
        }

    def _write_wav(self, path: Path, duration_frames: int = 4410) -> None:
        """Write a minimal valid WAV file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            wf.writeframes(struct.pack("<" + "h" * duration_frames, *([0] * duration_frames)))

    def test_collect_with_narration_files(self, tmp_path):
        config = self._make_config(tmp_path)
        narr_dir = tmp_path / "narration"
        narr_dir.mkdir(parents=True)
        self._write_wav(narr_dir / "seq00_narration.wav")
        self._write_wav(narr_dir / "seq01_narration.wav")

        rpt = ProductionReport(config, build_dir=tmp_path)
        rpt.collect(project_name="Test")

        assert len(rpt.sequences) >= 2
        seq_ids = [e.seq_id for e in rpt.sequences]
        assert "seq00" in seq_ids
        assert "seq01" in seq_ids

    def test_collect_detects_subtitles(self, tmp_path):
        config = self._make_config(tmp_path)
        narr_dir = tmp_path / "narration"
        narr_dir.mkdir(parents=True)
        self._write_wav(narr_dir / "seq00_narration.wav")

        srt_dir = tmp_path / "fr" / "subtitles"
        srt_dir.mkdir(parents=True)
        (srt_dir / "seq00.srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n")

        rpt = ProductionReport(config, build_dir=tmp_path)
        rpt.collect(project_name="Test")

        assert len(rpt.sequences) > 0
        seq = rpt.sequences[0]
        assert "fr" in seq.subtitles

    def test_to_dict_structure(self, tmp_path):
        config = self._make_config(tmp_path)
        rpt = ProductionReport(config, build_dir=tmp_path)
        rpt.collect(project_name="Test")
        d = rpt.to_dict()

        assert "generated_at" in d
        assert "tts_engine" in d
        assert "sequences" in d
        assert "total_clip_duration" in d
        assert "total_narration_duration" in d

    def test_print_ascii_no_crash(self, tmp_path):
        config = self._make_config(tmp_path)
        rpt = ProductionReport(config, build_dir=tmp_path)
        rpt.collect(project_name="Test")
        # Should not raise even with empty output dirs
        rpt._print_ascii()

    def test_json_serialisable(self, tmp_path):
        config = self._make_config(tmp_path)
        rpt = ProductionReport(config, build_dir=tmp_path)
        rpt.collect(project_name="Test")
        # Must not raise
        serialized = json.dumps(rpt.to_dict())
        assert len(serialized) > 0

    def test_empty_output_dir_no_crash(self, tmp_path):
        config = self._make_config(tmp_path)
        rpt = ProductionReport(config, build_dir=tmp_path)
        rpt.collect()
        assert rpt.sequences == []


# ===========================================================================
# CLI integration tests (smoke tests using Click test runner)
# ===========================================================================

from click.testing import CliRunner
from narractive.cli import cli


class TestCLIStatus:
    def test_status_no_config(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["--status"])
            # Should fail gracefully (no config.yaml), not crash with exception
            assert result.exit_code != 0 or "state" in result.output.lower()


class TestCLIReport:
    def _make_config_file(self, tmp_path):
        cfg = {
            "output": {"final_dir": str(tmp_path / "final")},
            "narration": {"engine": "edge-tts", "output_dir": str(tmp_path / "narration")},
        }
        import yaml  # type: ignore
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(cfg), encoding="utf-8")
        return config_path

    def test_report_command_json_flag(self, tmp_path):
        try:
            import yaml  # noqa
        except ImportError:
            pytest.skip("pyyaml not installed")

        runner = CliRunner()
        config_path = self._make_config_file(tmp_path)
        result = runner.invoke(
            cli,
            ["report", str(tmp_path), "--config", str(config_path), "--json"],
        )
        # Should produce valid JSON output
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "sequences" in data
        assert "tts_engine" in data

    def test_report_command_ascii(self, tmp_path):
        try:
            import yaml  # noqa
        except ImportError:
            pytest.skip("pyyaml not installed")

        runner = CliRunner()
        config_path = self._make_config_file(tmp_path)
        result = runner.invoke(
            cli,
            ["report", str(tmp_path), "--config", str(config_path)],
        )
        assert result.exit_code == 0, result.output

    def test_report_output_json_file(self, tmp_path):
        try:
            import yaml  # noqa
        except ImportError:
            pytest.skip("pyyaml not installed")

        runner = CliRunner()
        config_path = self._make_config_file(tmp_path)
        out_file = tmp_path / "report.json"
        result = runner.invoke(
            cli,
            [
                "report", str(tmp_path),
                "--config", str(config_path),
                "--output", str(out_file),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert "sequences" in data
