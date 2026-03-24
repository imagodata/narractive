"""
Narrator — TTS Audio Generation
=================================
Generates narration audio files for each video sequence using either
edge-tts (free, Microsoft voices), ElevenLabs (paid, higher quality),
F5-TTS (open-source, zero-shot voice cloning), XTTS v2 (Coqui TTS,
multilingual voice cloning), or Kokoro (ultra-fast local TTS, no cloning).

Optionally preprocesses text through :class:`TextPreprocessor` to improve
TTS pronunciation of acronyms, numbers, and proper nouns.

Usage::

    from narractive.core.narrator import Narrator
    narrator = Narrator(config["narration"])
    path = narrator.generate_narration("Your text here", "output/narration/seq00.mp3")
    duration = narrator.get_narration_duration(path)

    # With pronunciation preprocessing:
    narrator = Narrator(config["narration"], pronunciation_config=config["pronunciation"])
    path = narrator.generate_narration("Open the PDF", "output/narration/seq01.mp3", lang="fr")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from narractive.core.text_preprocessor import TextPreprocessor
# Re-export for convenience: `from narractive.core.narrator import register_tts_engine`
from narractive.core.tts_base import register_tts_engine as register_tts_engine  # noqa: F401

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reference audio preparation utilities
# ---------------------------------------------------------------------------


def _get_audio_info(audio_path: Path) -> dict:
    """
    Get audio file metadata via ffprobe.

    Parameters
    ----------
    audio_path : Path
        Path to the audio file to inspect.

    Returns
    -------
    dict
        Keys: ``sample_rate`` (int), ``channels`` (int), ``duration`` (float),
        ``codec`` (str).  Returns an empty dict if ffprobe is unavailable or
        the file cannot be analysed.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {}
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        fmt = data.get("format", {})
        return {
            "sample_rate": int(stream.get("sample_rate", 0)),
            "channels": int(stream.get("channels", 0)),
            "duration": float(fmt.get("duration", 0)),
            "codec": stream.get("codec_name", "unknown"),
        }
    except Exception as exc:
        logger.warning("ffprobe unavailable or error: %s", exc)
        return {}


def prepare_reference_audio(
    ref_audio: Path,
    target_sr: int = 24000,
    target_channels: int = 1,
    max_duration: float = 12.0,
    min_duration: float = 3.0,
) -> Path:
    """
    Prepare a voice-cloning reference audio for F5-TTS / XTTS v2.

    Applies the following transformations when needed:

    * Stereo to mono conversion
    * Resampling to *target_sr* (default 24 kHz)
    * Trimming to *max_duration* seconds
    * Peak normalisation via the ``loudnorm`` filter (-16 LUFS, -1 dB TP)

    The prepared file is cached next to the original as
    ``{stem}_prepared.wav`` and reused when it is newer than the source.

    Parameters
    ----------
    ref_audio : Path
        Path to the original reference audio file.
    target_sr : int, optional
        Target sample rate in Hz (default ``24000``).
    target_channels : int, optional
        Target number of channels (default ``1`` = mono).
    max_duration : float, optional
        Maximum duration in seconds (default ``12.0``).
    min_duration : float, optional
        Minimum recommended duration in seconds (default ``3.0``).
        A warning is logged if the source is shorter.

    Returns
    -------
    Path
        Path to the prepared file, or the original path if already conformant
        or if ffprobe/ffmpeg are not available.
    """
    prepared_path = ref_audio.parent / f"{ref_audio.stem}_prepared.wav"

    # Reuse cached prepared file if it is newer than the source
    if prepared_path.exists() and prepared_path.stat().st_mtime > ref_audio.stat().st_mtime:
        logger.info("Reference audio: reusing cached prepared file %s", prepared_path.name)
        return prepared_path

    info = _get_audio_info(ref_audio)
    if not info:
        logger.warning(
            "Cannot analyse %s (ffprobe unavailable?), using original file as-is",
            ref_audio.name,
        )
        return ref_audio

    needs_conversion = False
    reasons: list[str] = []

    if info["channels"] != target_channels:
        needs_conversion = True
        reasons.append(f"channels {info['channels']} -> {target_channels}")

    if info["sample_rate"] != target_sr:
        needs_conversion = True
        reasons.append(f"resample {info['sample_rate']}Hz -> {target_sr}Hz")

    if info["duration"] > max_duration:
        needs_conversion = True
        reasons.append(f"trim {info['duration']:.1f}s -> {max_duration:.1f}s")

    if info["duration"] < min_duration:
        logger.warning(
            "Reference audio too short (%.1fs < %.1fs). Recommended: 5-10 seconds.",
            info["duration"],
            min_duration,
        )

    if not needs_conversion:
        logger.info(
            "Reference audio already conformant (%dHz, %dch, %.1fs)",
            info["sample_rate"],
            info["channels"],
            info["duration"],
        )
        return ref_audio

    # Build ffmpeg conversion command
    logger.info("Preparing reference audio: %s", ", ".join(reasons))

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", str(ref_audio),
        "-ac", str(target_channels),
        "-ar", str(target_sr),
        "-sample_fmt", "s16",
        "-af", f"loudnorm=I=-16:TP=-1:LRA=11,atrim=0:{max_duration}",
        str(prepared_path),
    ]

    try:
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(
                "ffmpeg conversion failed: %s",
                result.stderr[-200:] if result.stderr else "unknown error",
            )
            return ref_audio

        # Verify the produced file
        prep_info = _get_audio_info(prepared_path)
        if prep_info:
            logger.info(
                "Reference audio prepared: %s (%dHz, %dch, %.1fs)",
                prepared_path.name,
                prep_info["sample_rate"],
                prep_info["channels"],
                prep_info["duration"],
            )
        return prepared_path

    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning(
            "ffmpeg unavailable: %s. Using original reference audio.", exc
        )
        return ref_audio


# ---------------------------------------------------------------------------
# Post-processing utilities
# ---------------------------------------------------------------------------


def postprocess_audio(
    audio_path: Path,
    target_lufs: float = -16.0,
    target_tp: float = -1.0,
) -> Path:
    """
    Post-process generated audio with EBU R128 loudness normalization.

    Uses ffmpeg's loudnorm filter to normalize perceived loudness.
    Overwrites the file in-place via a temporary file.

    Parameters
    ----------
    audio_path : Path
        Path to the audio file to normalize.
    target_lufs : float
        Target integrated loudness in LUFS (-16 = podcast/narration standard).
    target_tp : float
        Maximum true peak in dBTP (-1.0 = safe for all encoders).

    Returns
    -------
    Path
        Path to the normalized audio (same as input).
    """
    if not audio_path.exists():
        logger.warning("Audio file not found for normalization: %s", audio_path)
        return audio_path

    temp_path = audio_path.parent / f"{audio_path.stem}_postproc.wav"

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-af", f"loudnorm=I={target_lufs}:TP={target_tp}:LRA=11:print_format=summary",
        str(temp_path),
    ]

    try:
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(
                "Loudness normalization failed: %s",
                result.stderr[-200:] if result.stderr else "unknown error",
            )
            return audio_path

        # Replace original with normalized file
        temp_path.replace(audio_path)
        logger.info(
            "EBU R128 normalization applied to %s (target: %.0f LUFS, TP: %.0f dBTP)",
            audio_path.name, target_lufs, target_tp,
        )
        return audio_path

    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg timed out during loudness normalization of %s", audio_path.name)
        if temp_path.exists():
            temp_path.unlink()
        return audio_path

    except FileNotFoundError:
        logger.warning(
            "ffmpeg not found — skipping loudness normalization. "
            "Install ffmpeg to enable EBU R128 normalization."
        )
        if temp_path.exists():
            temp_path.unlink()
        return audio_path


class NarrationCache:
    """
    Content-addressed cache for narration audio files.

    Stores a JSON sidecar file (``.narration-cache.json``) alongside the
    generated audio.  Each entry records the SHA-256 hash of the generation
    inputs (text + engine + voice + lang + speed) so that unchanged sequences
    are skipped on subsequent runs.

    Parameters
    ----------
    cache_path : Path
        Path to the ``.narration-cache.json`` file.
    """

    CACHE_FILENAME = ".narration-cache.json"

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self._data: dict[str, dict] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load narration cache (%s): %s", self._path, exc)
                self._data = {}

    def save(self) -> None:
        """Persist the cache to disk."""
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.warning("Failed to save narration cache: %s", exc)

    # ------------------------------------------------------------------
    # Hash computation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_hash(text: str, engine: str, voice: str, lang: str, speed: str | float) -> str:
        """Return a SHA-256 hex digest of the generation inputs."""
        payload = f"{text}\x00{engine}\x00{voice}\x00{lang}\x00{speed}"
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    def is_cached(
        self,
        seq_id: str,
        text: str,
        engine: str,
        voice: str,
        lang: str,
        speed: str | float,
        audio_path: Path,
    ) -> bool:
        """Return True if the cached entry matches and the audio file exists."""
        entry = self._data.get(seq_id)
        if not entry:
            return False
        expected_hash = self.compute_hash(text, engine, voice, lang, speed)
        return (
            entry.get("hash") == expected_hash
            and audio_path.exists()
            and audio_path.stat().st_size > 0
        )

    def update(
        self,
        seq_id: str,
        text: str,
        engine: str,
        voice: str,
        lang: str,
        speed: str | float,
    ) -> None:
        """Record a successful generation in the cache."""
        self._data[seq_id] = {
            "hash": self.compute_hash(text, engine, voice, lang, speed),
            "engine": engine,
            "voice": voice,
            "lang": lang,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def for_output_dir(cls, output_dir: Path) -> "NarrationCache":
        """Return a :class:`NarrationCache` whose file lives in *output_dir*."""
        output_dir.mkdir(parents=True, exist_ok=True)
        return cls(output_dir / cls.CACHE_FILENAME)


class Narrator:
    """
    Generates TTS narration audio.

    Parameters
    ----------
    config : dict
        The 'narration' section from config.yaml.
    pronunciation_config : dict | None
        The ``pronunciation`` section from config.yaml. When provided, a
        :class:`~narractive.core.text_preprocessor.TextPreprocessor`
        is created to transform text before sending it to the TTS engine.
        See :class:`TextPreprocessor` for the expected YAML structure.
    """

    def __init__(
        self,
        config: dict,
        pronunciation_config: dict | None = None,
    ) -> None:
        self.engine: str = config.get("engine", "edge-tts")
        self.voice: str = config.get("voice", "fr-FR-HenriNeural")
        self.output_dir = Path(config.get("output_dir", "output/narration"))
        self.speed: str = config.get("speed", "+0%")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # F5-TTS specific config
        self.f5_ref_audio: Optional[str] = config.get("f5_ref_audio")
        self.f5_ref_text: str = config.get("f5_ref_text", "")
        self.f5_model: str = config.get("f5_model", "F5TTS_v1_Base")
        self.f5_speed: float = config.get("f5_speed", 1.0)
        self.f5_conda_env: str = config.get("f5_conda_env", "f5-tts")
        self.f5_remove_silence: bool = config.get("f5_remove_silence", False)
        # Advanced F5-TTS inference parameters
        self.f5_nfe_step: int = config.get("f5_nfe_step", 32)
        self.f5_cfg_strength: float = config.get("f5_cfg_strength", 2.0)
        self.f5_sway_sampling_coef: float = config.get("f5_sway_sampling_coef", -1.0)
        self.f5_cross_fade_duration: float = config.get("f5_cross_fade_duration", 0.15)
        self.f5_target_rms: float = config.get("f5_target_rms", 0.1)
        self.f5_seed: int = config.get("f5_seed", -1)
        self.f5_ckpt_file: str | None = config.get("f5_ckpt_file")
        self.f5_vocab_file: str | None = config.get("f5_vocab_file")

        # XTTS v2 specific config
        self.xtts_ref_audio: Optional[str] = config.get("xtts_ref_audio")
        self.xtts_language: str = config.get("xtts_language", "en")
        self.xtts_speed: float = config.get("xtts_speed", 1.0)
        self.xtts_gpu: bool = config.get("xtts_gpu", True)
        self.xtts_conda_env: str = config.get("xtts_conda_env", "xtts")

        # Kokoro TTS specific config
        self.kokoro_voice: str = config.get("kokoro_voice", "")
        self.kokoro_lang: str = config.get("kokoro_lang", "en")
        self.kokoro_speed: float = config.get("kokoro_speed", 1.0)
        self.kokoro_conda_env: str | None = config.get("kokoro_conda_env")
        # Kokoro voice mixing
        self.kokoro_voices: list[dict] = config.get("kokoro", {}).get("voices", [])
        self.kokoro_voice_file: str | None = config.get("kokoro", {}).get("voice_file")

        # OpenAI TTS specific config
        _openai_cfg: dict = config.get("openai", {})
        self.openai_api_key: str | None = _openai_cfg.get("api_key")
        self.openai_model: str = _openai_cfg.get("model", "tts-1-hd")
        self.openai_voice: str = _openai_cfg.get("voice", "alloy")
        self.openai_speed: float = float(_openai_cfg.get("speed", 1.0))
        self.openai_format: str = _openai_cfg.get("format", "mp3")

        # Loudness normalization (EBU R128)
        self.normalize_loudness: bool = config.get("normalize_loudness", False)
        self.target_lufs: float = config.get("target_lufs", -16.0)
        self.target_tp: float = config.get("target_tp", -1.0)

        # Text preprocessor for pronunciation improvement
        self.preprocessor: TextPreprocessor | None = None
        if pronunciation_config is not None:
            self.preprocessor = TextPreprocessor(config=pronunciation_config)
            logger.info("Text preprocessor enabled for TTS pronunciation")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_narration(
        self,
        text: str,
        output_path: str | Path,
        voice: Optional[str] = None,
        lang: str = "fr",
    ) -> Path:
        """
        Generate TTS audio for the given text.

        Parameters
        ----------
        text : str
            Raw narration text.
        output_path : str | Path
            Destination file path for the generated audio.
        voice : str | None
            Override voice (engine-specific). Falls back to ``self.voice``.
        lang : str
            Language code for text preprocessing (``"fr"``, ``"en"``,
            ``"pt"``). Only used when a ``pronunciation_config`` was
            provided at init time. Defaults to ``"fr"``.

        Returns
        -------
        Path
            Path to the generated audio file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        voice = voice or self.voice

        # Preprocess text for better TTS pronunciation
        if self.preprocessor is not None:
            text = self.preprocessor.preprocess(text, lang=lang)
            logger.debug("Preprocessed text for TTS: %s", text[:120])

        if self.engine == "edge-tts":
            result = self._generate_edge_tts(text, output_path, voice)
        elif self.engine == "elevenlabs":
            result = self._generate_elevenlabs(text, output_path, voice)
        elif self.engine == "f5-tts":
            result = self._generate_f5_tts(text, output_path)
        elif self.engine in ("xtts", "xtts-v2", "coqui"):
            result = self._generate_xtts(text, output_path)
        elif self.engine == "kokoro":
            result = self._generate_kokoro(text, output_path, lang=lang)
        elif self.engine == "openai":
            result = self._generate_openai(text, output_path)
        else:
            # Try the plugin registry before giving up
            result = self._generate_plugin(text, output_path, lang=lang)
            if result is None:
                raise ValueError(
                    f"Unknown TTS engine: {self.engine!r}. "
                    "Built-in engines: edge-tts, elevenlabs, f5-tts, xtts-v2, kokoro, openai. "
                    "Register a custom engine with register_tts_engine() or via the "
                    "'narractive.tts' entry-point group."
                )

        # Post-process: EBU R128 loudness normalization (opt-in)
        if self.normalize_loudness:
            result = postprocess_audio(
                result,
                target_lufs=self.target_lufs,
                target_tp=self.target_tp,
            )

        return result

    def generate_all_narrations(
        self,
        script_dict: dict[str, str],
        output_dir: Optional[str | Path] = None,
        lang: str = "fr",
        force: bool = False,
    ) -> dict[str, Path]:
        """
        Batch-generate narration audio for all sequences.

        Skips generation when a matching cache entry exists and the audio file
        is present (content-addressed cache keyed on text + engine + voice +
        lang + speed).  Pass ``force=True`` to bypass the cache entirely.

        Parameters
        ----------
        script_dict : dict[str, str]
            Mapping of sequence_id -> narration text.
        output_dir : str | Path | None
            Output directory.  Falls back to ``self.output_dir``.
        lang : str
            Language code.
        force : bool
            When ``True``, regenerate all files regardless of cache state.
        """
        out_dir = Path(output_dir) if output_dir else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        cache = NarrationCache.for_output_dir(out_dir)
        results: dict[str, Path] = {}

        for seq_id, text in script_dict.items():
            output_path = out_dir / f"{seq_id}_narration.mp3"
            effective_voice = self.voice

            if not force and cache.is_cached(
                seq_id, text, self.engine, effective_voice, lang, self.speed, output_path
            ):
                logger.info("[CACHED] %s — skipping TTS generation", seq_id)
                results[seq_id] = output_path
                continue

            logger.info("[GENERATING] %s...", seq_id)
            try:
                results[seq_id] = self.generate_narration(text, output_path, lang=lang)
                cache.update(seq_id, text, self.engine, effective_voice, lang, self.speed)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to generate narration for %s: %s", seq_id, exc)

        cache.save()
        return results

    def get_narration_duration(self, audio_path: str | Path) -> float:
        """Return the duration of an audio file in seconds."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            logger.warning("Audio file not found: %s", audio_path)
            return 0.0

        try:
            from mutagen.mp3 import MP3  # type: ignore
            from mutagen.wave import WAVE  # type: ignore

            if audio_path.suffix.lower() == ".mp3":
                audio = MP3(audio_path)
            elif audio_path.suffix.lower() in (".wav",):
                audio = WAVE(audio_path)
            else:
                raise ValueError(f"Unsupported format: {audio_path.suffix}")
            return float(audio.info.length)
        except ImportError:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.debug("mutagen failed: %s", exc)

        return self._ffprobe_duration(audio_path)

    def list_voices(self) -> list[dict]:
        """List available edge-tts voices."""
        if self.engine != "edge-tts":
            raise RuntimeError("list_voices() only supports edge-tts engine.")
        try:
            import edge_tts  # type: ignore
            voices = asyncio.run(edge_tts.list_voices())
            return voices
        except ImportError:
            raise ImportError("edge-tts not installed. Run: pip install edge-tts")

    # ------------------------------------------------------------------
    # Engine implementations
    # ------------------------------------------------------------------

    def _generate_edge_tts(self, text: str, output_path: Path, voice: str) -> Path:
        try:
            import edge_tts  # type: ignore
        except ImportError:
            raise ImportError("edge-tts not installed. Run: pip install edge-tts")

        async def _run():
            communicate = edge_tts.Communicate(text, voice, rate=self.speed)
            await communicate.save(str(output_path))

        asyncio.run(_run())
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"edge-tts produced empty/missing file: {output_path}")
        logger.info("edge-tts generated: %s (%.1fs)", output_path.name,
                    self.get_narration_duration(output_path))
        return output_path

    def _generate_elevenlabs(self, text: str, output_path: Path, voice: str) -> Path:
        import os
        try:
            from elevenlabs import generate, save  # type: ignore
        except ImportError:
            raise ImportError("elevenlabs not installed. Run: pip install elevenlabs")

        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise EnvironmentError("ELEVENLABS_API_KEY environment variable not set.")

        audio = generate(text=text, voice=voice, api_key=api_key)
        save(audio, str(output_path))
        logger.info("ElevenLabs generated: %s", output_path.name)
        return output_path

    def _generate_f5_tts(self, text: str, output_path: Path) -> Path:
        if not self.f5_ref_audio:
            raise ValueError(
                "f5_ref_audio must be set in narration config when using f5-tts engine."
            )

        ref_audio_path = Path(self.f5_ref_audio).resolve()
        if not ref_audio_path.exists():
            raise FileNotFoundError(f"F5-TTS reference audio not found: {ref_audio_path}")

        # Prepare reference audio (mono, 24kHz, trimmed, normalized)
        ref_audio_path = prepare_reference_audio(ref_audio_path)

        wav_output = output_path.with_suffix(".wav").resolve()

        bridge_script = Path(__file__).parent.parent / "bridges" / "f5_tts_bridge.py"
        if not bridge_script.exists():
            raise FileNotFoundError(f"F5-TTS bridge script not found: {bridge_script}")

        conda_python = Path.home() / "miniconda3" / "envs" / self.f5_conda_env / "python.exe"
        if not conda_python.exists():
            raise RuntimeError(
                f"Conda env Python not found: {conda_python}\n"
                f"Create the environment:\n"
                f"  conda create -n {self.f5_conda_env} python=3.11 -y\n"
                f"  conda activate {self.f5_conda_env}\n"
                "  pip install f5-tts torch torchaudio"
            )

        import tempfile
        gen_text_file = Path(tempfile.mktemp(suffix="_gen.txt"))
        ref_text_file = Path(tempfile.mktemp(suffix="_ref.txt"))
        gen_text_file.write_text(text, encoding="utf-8")
        ref_text_file.write_text(self.f5_ref_text, encoding="utf-8")

        cmd = [
            str(conda_python),
            "-X", "utf8",
            str(bridge_script),
            "--model", self.f5_model,
            "--ref_audio", str(ref_audio_path),
            "--ref_text_file", str(ref_text_file),
            "--gen_text_file", str(gen_text_file),
            "--output_file", str(wav_output),
            "--speed", str(self.f5_speed),
            # Advanced inference parameters
            "--nfe_step", str(self.f5_nfe_step),
            "--cfg_strength", str(self.f5_cfg_strength),
            "--sway_sampling_coef", str(self.f5_sway_sampling_coef),
            "--cross_fade_duration", str(self.f5_cross_fade_duration),
            "--target_rms", str(self.f5_target_rms),
            "--seed", str(self.f5_seed),
        ]
        if self.f5_remove_silence:
            cmd.append("--remove_silence")
        if self.f5_ckpt_file:
            cmd.extend(["--ckpt_file", self.f5_ckpt_file])
        if self.f5_vocab_file:
            cmd.extend(["--vocab_file", self.f5_vocab_file])

        logger.info("F5-TTS generating: %s (conda env: %s)", output_path.name, self.f5_conda_env)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"F5-TTS timed out after 300s for: {output_path.name}")
        finally:
            gen_text_file.unlink(missing_ok=True)
            ref_text_file.unlink(missing_ok=True)

        if result.returncode != 0:
            raise RuntimeError(f"F5-TTS CLI failed (exit {result.returncode}):\n{result.stderr[:500]}")

        if not wav_output.exists() or wav_output.stat().st_size == 0:
            raise RuntimeError(f"F5-TTS produced empty/missing file: {wav_output}")

        if output_path.suffix.lower() == ".mp3":
            self._wav_to_mp3(wav_output, output_path)
            wav_output.unlink(missing_ok=True)
        else:
            output_path = wav_output

        logger.info("F5-TTS generated: %s (%.1fs)", output_path.name,
                    self.get_narration_duration(output_path))
        return output_path

    def _generate_xtts(self, text: str, output_path: Path) -> Path:
        """Generate audio using XTTS v2 (Coqui TTS) via bridge subprocess."""
        if not self.xtts_ref_audio:
            raise ValueError(
                "xtts_ref_audio must be set in narration config when using xtts-v2 engine."
            )

        ref_audio_path = Path(self.xtts_ref_audio).resolve()
        if not ref_audio_path.exists():
            raise FileNotFoundError(f"XTTS reference audio not found: {ref_audio_path}")

        # Prepare reference audio (mono, 24kHz, trimmed, normalized)
        ref_audio_path = prepare_reference_audio(ref_audio_path)

        wav_output = output_path.with_suffix(".wav").resolve()

        bridge_script = Path(__file__).parent.parent / "bridges" / "xtts_bridge.py"
        if not bridge_script.exists():
            raise FileNotFoundError(f"XTTS bridge script not found: {bridge_script}")

        # Find Python in conda env or fall back to system Python
        conda_python = Path.home() / "miniconda3" / "envs" / self.xtts_conda_env / "python.exe"
        if not conda_python.exists():
            # Try Linux path
            conda_python = (
                Path.home() / "miniconda3" / "envs" / self.xtts_conda_env / "bin" / "python"
            )
        if not conda_python.exists():
            raise RuntimeError(
                f"Conda env Python not found for '{self.xtts_conda_env}'.\n"
                f"Create the environment:\n"
                f"  conda create -n {self.xtts_conda_env} python=3.11 -y\n"
                f"  conda activate {self.xtts_conda_env}\n"
                "  pip install TTS torch torchaudio"
            )

        import tempfile

        text_file = Path(tempfile.mktemp(suffix="_xtts.txt"))
        text_file.write_text(text, encoding="utf-8")

        cmd = [
            str(conda_python),
            "-X", "utf8",
            str(bridge_script),
            "--ref_audio", str(ref_audio_path),
            "--text_file", str(text_file),
            "--output_file", str(wav_output),
            "--language", self.xtts_language,
            "--speed", str(self.xtts_speed),
        ]
        if self.xtts_gpu:
            cmd.append("--gpu")

        logger.info(
            "XTTS v2 generating: %s (lang=%s, conda=%s)",
            output_path.name, self.xtts_language, self.xtts_conda_env,
        )

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"XTTS v2 timed out after 300s for: {output_path.name}")
        finally:
            text_file.unlink(missing_ok=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"XTTS v2 failed (exit {result.returncode}):\n{result.stderr[:500]}"
            )

        if not wav_output.exists() or wav_output.stat().st_size == 0:
            raise RuntimeError(f"XTTS v2 produced empty/missing file: {wav_output}")

        if output_path.suffix.lower() == ".mp3":
            self._wav_to_mp3(wav_output, output_path)
            wav_output.unlink(missing_ok=True)
        else:
            output_path = wav_output

        logger.info(
            "XTTS v2 generated: %s (%.1fs)",
            output_path.name, self.get_narration_duration(output_path),
        )
        return output_path

    def _generate_kokoro(self, text: str, output_path: Path, lang: str = "en") -> Path:
        """Generate audio using Kokoro TTS (ultra-fast, local, no voice cloning)."""
        wav_output = output_path.with_suffix(".wav").resolve()

        bridge_script = Path(__file__).parent.parent / "bridges" / "kokoro_bridge.py"
        if not bridge_script.exists():
            raise FileNotFoundError(f"Kokoro bridge script not found: {bridge_script}")

        # Use kokoro_lang from config, fallback to the lang parameter
        kokoro_lang = self.kokoro_lang or lang

        import tempfile

        text_file = Path(tempfile.mktemp(suffix="_kokoro.txt"))
        text_file.write_text(text, encoding="utf-8")

        # Determine Python executable: conda env or current interpreter
        if self.kokoro_conda_env:
            conda_python = (
                Path.home() / "miniconda3" / "envs" / self.kokoro_conda_env / "bin" / "python"
            )
            if not conda_python.exists():
                # Try Windows path
                conda_python = (
                    Path.home()
                    / "miniconda3"
                    / "envs"
                    / self.kokoro_conda_env
                    / "python.exe"
                )
            if not conda_python.exists():
                raise RuntimeError(
                    f"Conda env Python not found for '{self.kokoro_conda_env}'.\n"
                    f"Create the environment:\n"
                    f"  conda create -n {self.kokoro_conda_env} python=3.11 -y\n"
                    f"  conda activate {self.kokoro_conda_env}\n"
                    "  pip install kokoro soundfile"
                )
            python_cmd = str(conda_python)
        else:
            python_cmd = sys.executable

        cmd = [
            python_cmd,
            "-X", "utf8",
            str(bridge_script),
            "--text_file", str(text_file),
            "--output_file", str(wav_output),
            "--lang", kokoro_lang,
            "--speed", str(self.kokoro_speed),
        ]

        # Voice selection priority: voice_file > voices (mixing) > voice > default
        if self.kokoro_voice_file:
            cmd.extend(["--voice_file", self.kokoro_voice_file])
        elif self.kokoro_voices:
            import json as _json
            cmd.extend(["--voices", _json.dumps(self.kokoro_voices)])
        elif self.kokoro_voice:
            cmd.extend(["--voice", self.kokoro_voice])

        logger.info(
            "Kokoro generating: %s (lang=%s, voice=%s)",
            output_path.name, kokoro_lang, self.kokoro_voice or "default",
        )

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Kokoro timed out after 120s for: {output_path.name}")
        finally:
            text_file.unlink(missing_ok=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"Kokoro failed (exit {result.returncode}):\n{result.stderr[:500]}"
            )

        if not wav_output.exists() or wav_output.stat().st_size == 0:
            raise RuntimeError(f"Kokoro produced empty/missing file: {wav_output}")

        if output_path.suffix.lower() == ".mp3":
            self._wav_to_mp3(wav_output, output_path)
            wav_output.unlink(missing_ok=True)
        else:
            output_path = wav_output

        logger.info(
            "Kokoro generated: %s (%.1fs)",
            output_path.name, self.get_narration_duration(output_path),
        )
        return output_path

    def _generate_openai(self, text: str, output_path: Path) -> Path:
        """Generate audio using OpenAI TTS API (tts-1 / tts-1-hd)."""
        import os

        try:
            import openai  # type: ignore
        except ImportError:
            raise ImportError(
                "openai not installed. Run: pip install 'narractive[openai]'"
            )

        api_key = self.openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or add 'api_key' under the 'openai' section in your config."
            )

        _valid_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
        voice = self.openai_voice if self.openai_voice in _valid_voices else "alloy"
        if self.openai_voice not in _valid_voices:
            logger.warning(
                "Invalid OpenAI voice '%s'. Valid voices: %s. Falling back to 'alloy'.",
                self.openai_voice,
                ", ".join(sorted(_valid_voices)),
            )

        _valid_models = {"tts-1", "tts-1-hd"}
        model = self.openai_model if self.openai_model in _valid_models else "tts-1-hd"

        logger.info(
            "OpenAI TTS generating: %s (model=%s, voice=%s, format=%s)",
            output_path.name, model, voice, self.openai_format,
        )

        client = openai.OpenAI(api_key=api_key)
        response = client.audio.speech.create(
            model=model,
            voice=voice,  # type: ignore[arg-type]
            input=text,
            response_format=self.openai_format,  # type: ignore[arg-type]
            speed=self.openai_speed,
        )

        # Stream directly to file
        out_path = output_path.with_suffix(f".{self.openai_format}")
        with open(out_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=4096):
                f.write(chunk)

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError(f"OpenAI TTS produced empty/missing file: {out_path}")

        logger.info(
            "OpenAI TTS generated: %s (%.1fs)",
            out_path.name, self.get_narration_duration(out_path),
        )
        return out_path

    def _generate_plugin(
        self, text: str, output_path: Path, lang: str = "fr"
    ) -> "Path | None":
        """
        Attempt to generate audio using a registered :class:`~narractive.core.tts_base.TTSEngine` plugin.

        Returns the output :class:`Path` on success, or ``None`` when no plugin
        is registered for ``self.engine``.
        """
        from narractive.core.tts_base import get_tts_engine, load_entry_point_plugins

        # Ensure entry-point plugins are loaded (idempotent)
        load_entry_point_plugins()

        engine_cls = get_tts_engine(self.engine)
        if engine_cls is None:
            return None

        engine_instance = engine_cls()
        logger.info("Using plugin TTS engine '%s': %s", self.engine, engine_cls.__name__)
        return engine_instance.generate(text, output_path, lang=lang)

    @staticmethod
    def _wav_to_mp3(wav_path: Path, mp3_path: Path) -> None:
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(wav_path), "-q:a", "2", str(mp3_path)],
                capture_output=True, check=True,
            )
        except FileNotFoundError:
            raise RuntimeError("ffmpeg not found. Install ffmpeg to convert WAV to MP3.")

    def _ffprobe_duration(self, audio_path: Path) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(audio_path)],
                capture_output=True, text=True, check=True,
            )
            data = json.loads(result.stdout)
            for stream in data.get("streams", []):
                if "duration" in stream:
                    return float(stream["duration"])
        except Exception as exc:  # noqa: BLE001
            logger.error("ffprobe failed: %s", exc)
        return 0.0


# ---------------------------------------------------------------------------
# Narration texts — loaded from narrations.yaml
# ---------------------------------------------------------------------------

def load_narrations_from_yaml(yaml_path: str | Path) -> dict[str, dict[str, str]]:
    """Load narrations from a YAML file."""
    import yaml
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        logger.warning("narrations.yaml not found at %s", yaml_path)
        return {}
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_narration_texts(
    yaml_path: str | Path,
    video: str | None = None,
) -> dict[str, str]:
    """Return the narration texts dict for the given video script."""
    data = load_narrations_from_yaml(yaml_path)
    if video and video in data:
        return data[video]
    return data.get("original", {})


def load_narrations_multilingual(
    narrations_dir: str | Path,
    lang: str,
) -> dict[str, str]:
    """
    Load narrations from a per-language YAML file.

    Expects files named ``{lang}.yaml`` inside *narrations_dir*,
    where each key is a sequence_id and the value is the narration text.

    Parameters
    ----------
    narrations_dir : str | Path
        Directory containing ``fr.yaml``, ``en.yaml``, etc.
    lang : str
        Language code.

    Returns
    -------
    dict[str, str]
        Mapping of sequence_id -> narration text.
    """
    import yaml

    yaml_path = Path(narrations_dir) / f"{lang}.yaml"
    if not yaml_path.exists():
        logger.warning("Narration file not found: %s", yaml_path)
        return {}
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return {}
    # Filter to only string values (skip metadata keys)
    return {k: v for k, v in data.items() if isinstance(v, str)}
