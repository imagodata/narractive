"""Tests for the Narrator class — engine selection, config, duration, preprocessing."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from narractive.core.narrator import (
    Narrator,
    _get_audio_info,
    postprocess_audio,
    prepare_reference_audio,
    get_narration_texts,
    load_narrations_multilingual,
)


# ---------------------------------------------------------------------------
# Narrator init and config
# ---------------------------------------------------------------------------


class TestNarratorInit:
    def test_defaults(self, tmp_path):
        n = Narrator({"output_dir": str(tmp_path / "out")})
        assert n.engine == "edge-tts"
        assert n.voice == "fr-FR-HenriNeural"
        assert n.speed == "+0%"
        assert n.normalize_loudness is False

    def test_custom_engine(self, tmp_path):
        n = Narrator({"engine": "elevenlabs", "voice": "test_voice", "output_dir": str(tmp_path)})
        assert n.engine == "elevenlabs"
        assert n.voice == "test_voice"

    def test_creates_output_dir(self, tmp_path):
        Narrator({"output_dir": str(tmp_path / "narration")})
        assert (tmp_path / "narration").is_dir()

    def test_f5_config(self, tmp_path):
        n = Narrator({
            "engine": "f5-tts",
            "output_dir": str(tmp_path),
            "f5_ref_audio": "ref.wav",
            "f5_ref_text": "reference",
            "f5_model": "CustomModel",
            "f5_speed": 1.2,
            "f5_conda_env": "my-env",
            "f5_remove_silence": True,
            "f5_nfe_step": 64,
            "f5_cfg_strength": 3.0,
            "f5_seed": 42,
        })
        assert n.f5_ref_audio == "ref.wav"
        assert n.f5_model == "CustomModel"
        assert n.f5_speed == 1.2
        assert n.f5_remove_silence is True
        assert n.f5_nfe_step == 64
        assert n.f5_cfg_strength == 3.0
        assert n.f5_seed == 42

    def test_xtts_config(self, tmp_path):
        n = Narrator({
            "engine": "xtts-v2",
            "output_dir": str(tmp_path),
            "xtts_ref_audio": "ref.wav",
            "xtts_language": "fr",
            "xtts_speed": 0.9,
            "xtts_gpu": False,
        })
        assert n.xtts_ref_audio == "ref.wav"
        assert n.xtts_language == "fr"
        assert n.xtts_speed == 0.9
        assert n.xtts_gpu is False

    def test_kokoro_config(self, tmp_path):
        n = Narrator({
            "engine": "kokoro",
            "output_dir": str(tmp_path),
            "kokoro_voice": "af_heart",
            "kokoro_lang": "en",
            "kokoro_speed": 1.1,
        })
        assert n.kokoro_voice == "af_heart"
        assert n.kokoro_lang == "en"
        assert n.kokoro_speed == 1.1

    def test_loudness_normalization_config(self, tmp_path):
        n = Narrator({
            "output_dir": str(tmp_path),
            "normalize_loudness": True,
            "target_lufs": -14.0,
            "target_tp": -0.5,
        })
        assert n.normalize_loudness is True
        assert n.target_lufs == -14.0
        assert n.target_tp == -0.5

    def test_preprocessor_enabled(self, tmp_path):
        pron = {"acronyms": {}, "spelled": {}, "proper_nouns": {}}
        n = Narrator({"output_dir": str(tmp_path)}, pronunciation_config=pron)
        assert n.preprocessor is not None

    def test_preprocessor_disabled_by_default(self, tmp_path):
        n = Narrator({"output_dir": str(tmp_path)})
        assert n.preprocessor is None


# ---------------------------------------------------------------------------
# Engine routing
# ---------------------------------------------------------------------------


class TestNarratorEngineRouting:
    def test_unknown_engine_raises(self, tmp_path):
        n = Narrator({"engine": "nonexistent", "output_dir": str(tmp_path)})
        with pytest.raises(ValueError, match="Unknown TTS engine"):
            n.generate_narration("Hello", str(tmp_path / "test.mp3"))

    def test_f5_without_ref_audio_raises(self, tmp_path):
        n = Narrator({"engine": "f5-tts", "output_dir": str(tmp_path)})
        with pytest.raises(ValueError, match="f5_ref_audio"):
            n.generate_narration("Hello", str(tmp_path / "test.mp3"))

    def test_xtts_without_ref_audio_raises(self, tmp_path):
        n = Narrator({"engine": "xtts-v2", "output_dir": str(tmp_path)})
        with pytest.raises(ValueError, match="xtts_ref_audio"):
            n.generate_narration("Hello", str(tmp_path / "test.mp3"))

    def test_list_voices_non_edge_raises(self, tmp_path):
        n = Narrator({"engine": "elevenlabs", "output_dir": str(tmp_path)})
        with pytest.raises(RuntimeError, match="only supports edge-tts"):
            n.list_voices()


# ---------------------------------------------------------------------------
# generate_all_narrations
# ---------------------------------------------------------------------------


class TestGenerateAllNarrations:
    def test_empty_dict(self, tmp_path):
        n = Narrator({"output_dir": str(tmp_path)})
        results = n.generate_all_narrations({})
        assert results == {}

    @patch.object(Narrator, "generate_narration")
    def test_batch_generation(self, mock_gen, tmp_path):
        mock_gen.return_value = tmp_path / "out.mp3"
        n = Narrator({"output_dir": str(tmp_path)})
        scripts = {"seq01": "Hello", "seq02": "World"}
        results = n.generate_all_narrations(scripts)
        assert mock_gen.call_count == 2
        assert len(results) == 2

    @patch.object(Narrator, "generate_narration", side_effect=RuntimeError("TTS fail"))
    def test_batch_continues_on_error(self, mock_gen, tmp_path):
        n = Narrator({"output_dir": str(tmp_path)})
        scripts = {"seq01": "Hello", "seq02": "World"}
        results = n.generate_all_narrations(scripts)
        # Both should be attempted, but both fail
        assert mock_gen.call_count == 2
        assert len(results) == 0


# ---------------------------------------------------------------------------
# get_narration_duration
# ---------------------------------------------------------------------------


class TestGetNarrationDuration:
    def test_nonexistent_file(self, tmp_path):
        n = Narrator({"output_dir": str(tmp_path)})
        dur = n.get_narration_duration(tmp_path / "missing.mp3")
        assert dur == 0.0

    @patch("subprocess.run")
    def test_ffprobe_fallback(self, mock_run, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"streams": [{"duration": "5.5"}]}),
        )
        n = Narrator({"output_dir": str(tmp_path)})
        # mutagen will fail on empty file, so it falls back to ffprobe
        dur = n.get_narration_duration(audio_file)
        assert dur == 5.5


# ---------------------------------------------------------------------------
# _get_audio_info
# ---------------------------------------------------------------------------


class TestGetAudioInfo:
    @patch("subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "streams": [{"sample_rate": "44100", "channels": "2", "codec_name": "mp3"}],
                "format": {"duration": "10.5"},
            }),
        )
        info = _get_audio_info(Path("test.mp3"))
        assert info["sample_rate"] == 44100
        assert info["channels"] == 2
        assert info["duration"] == 10.5
        assert info["codec"] == "mp3"

    @patch("subprocess.run")
    def test_ffprobe_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        info = _get_audio_info(Path("test.mp3"))
        assert info == {}

    @patch("subprocess.run", side_effect=FileNotFoundError("no ffprobe"))
    def test_ffprobe_not_found(self, mock_run):
        info = _get_audio_info(Path("test.mp3"))
        assert info == {}


# ---------------------------------------------------------------------------
# postprocess_audio
# ---------------------------------------------------------------------------


class TestPostprocessAudio:
    def test_missing_file(self, tmp_path):
        result = postprocess_audio(tmp_path / "missing.wav")
        assert result == tmp_path / "missing.wav"

    @patch("subprocess.run")
    def test_success(self, mock_run, tmp_path):
        audio = tmp_path / "test.wav"
        audio.touch()
        postproc = tmp_path / "test_postproc.wav"
        # Simulate ffmpeg creating the temp file
        def create_temp(*args, **kwargs):
            postproc.touch()
            return MagicMock(returncode=0)
        mock_run.side_effect = create_temp
        result = postprocess_audio(audio)
        assert result == audio

    @patch("subprocess.run")
    def test_ffmpeg_failure(self, mock_run, tmp_path):
        audio = tmp_path / "test.wav"
        audio.touch()
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        result = postprocess_audio(audio)
        # Should return original on failure
        assert result == audio

    @patch("subprocess.run", side_effect=FileNotFoundError("no ffmpeg"))
    def test_ffmpeg_not_found(self, mock_run, tmp_path):
        audio = tmp_path / "test.wav"
        audio.touch()
        result = postprocess_audio(audio)
        assert result == audio

    @patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("ffmpeg", 30))
    def test_ffmpeg_timeout(self, mock_run, tmp_path):
        audio = tmp_path / "test.wav"
        audio.touch()
        result = postprocess_audio(audio)
        assert result == audio


# ---------------------------------------------------------------------------
# prepare_reference_audio
# ---------------------------------------------------------------------------


class TestPrepareReferenceAudio:
    @patch("narractive.core.narrator._get_audio_info", return_value={})
    def test_no_ffprobe(self, mock_info, tmp_path):
        ref = tmp_path / "ref.wav"
        ref.touch()
        result = prepare_reference_audio(ref)
        assert result == ref

    @patch("narractive.core.narrator._get_audio_info")
    def test_already_conformant(self, mock_info, tmp_path):
        ref = tmp_path / "ref.wav"
        ref.touch()
        mock_info.return_value = {
            "sample_rate": 24000,
            "channels": 1,
            "duration": 8.0,
            "codec": "pcm_s16le",
        }
        result = prepare_reference_audio(ref)
        assert result == ref

    @patch("subprocess.run")
    @patch("narractive.core.narrator._get_audio_info")
    def test_needs_conversion(self, mock_info, mock_run, tmp_path):
        ref = tmp_path / "ref.wav"
        ref.touch()
        prepared = tmp_path / "ref_prepared.wav"
        mock_info.side_effect = [
            {"sample_rate": 44100, "channels": 2, "duration": 8.0, "codec": "pcm_s16le"},
            {"sample_rate": 24000, "channels": 1, "duration": 8.0, "codec": "pcm_s16le"},
        ]
        def create_prepared(*args, **kwargs):
            prepared.touch()
            return MagicMock(returncode=0)
        mock_run.side_effect = create_prepared
        result = prepare_reference_audio(ref)
        assert result == prepared

    @patch("narractive.core.narrator._get_audio_info")
    def test_too_short_warning(self, mock_info, tmp_path):
        ref = tmp_path / "ref.wav"
        ref.touch()
        mock_info.return_value = {
            "sample_rate": 24000,
            "channels": 1,
            "duration": 1.0,
            "codec": "pcm_s16le",
        }
        # Should log a warning but still return the file
        result = prepare_reference_audio(ref, min_duration=3.0)
        assert result == ref

    @patch("narractive.core.narrator._get_audio_info")
    def test_cached_prepared_reused(self, mock_info, tmp_path):
        ref = tmp_path / "ref.wav"
        ref.write_text("original")
        prepared = tmp_path / "ref_prepared.wav"
        prepared.write_text("prepared")
        # Make prepared newer
        import os
        os.utime(ref, (1000, 1000))
        os.utime(prepared, (2000, 2000))
        result = prepare_reference_audio(ref)
        assert result == prepared
        mock_info.assert_not_called()


# ---------------------------------------------------------------------------
# Narration text loading
# ---------------------------------------------------------------------------


class TestNarrationLoading:
    def test_get_narration_texts_missing_file(self, tmp_path):
        result = get_narration_texts(tmp_path / "missing.yaml")
        assert result == {}

    def test_load_narrations_multilingual_missing(self, tmp_path):
        result = load_narrations_multilingual(tmp_path, "fr")
        assert result == {}

    def test_load_narrations_multilingual_valid(self, tmp_path):
        yaml_file = tmp_path / "fr.yaml"
        yaml_file.write_text("seq01: Hello\nseq02: World\nmetadata: 42\n")
        result = load_narrations_multilingual(tmp_path, "fr")
        assert result == {"seq01": "Hello", "seq02": "World"}
        # metadata (int) should be filtered out
        assert "metadata" not in result


# ---------------------------------------------------------------------------
# Text preprocessing integration
# ---------------------------------------------------------------------------


class TestNarratorPreprocessing:
    @patch.object(Narrator, "_generate_edge_tts")
    def test_preprocessing_applied(self, mock_gen, tmp_path):
        mock_gen.return_value = tmp_path / "out.mp3"
        pron = {
            "acronyms": {"QGIS": {"fr": "Q. GIS"}},
            "spelled": {},
            "proper_nouns": {},
        }
        n = Narrator({"output_dir": str(tmp_path)}, pronunciation_config=pron)
        n.generate_narration("Open QGIS", str(tmp_path / "test.mp3"), lang="fr")
        # The text passed to engine should have QGIS replaced
        called_text = mock_gen.call_args[0][0]
        assert "Q. GIS" in called_text

    @patch.object(Narrator, "_generate_edge_tts")
    def test_no_preprocessing_without_config(self, mock_gen, tmp_path):
        mock_gen.return_value = tmp_path / "out.mp3"
        n = Narrator({"output_dir": str(tmp_path)})
        n.generate_narration("Open QGIS", str(tmp_path / "test.mp3"))
        called_text = mock_gen.call_args[0][0]
        assert called_text == "Open QGIS"
