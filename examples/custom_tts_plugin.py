"""
Custom TTS Engine Plugin Example
=================================
This file demonstrates how to write a custom TTS engine for Narractive.

Usage
-----
1. Define a subclass of :class:`TTSEngine` with a unique ``engine_name``.
2. Implement the :meth:`generate` method.
3. Register the engine at startup (e.g. in a ``conftest.py``, a project
   ``__init__.py``, or via the ``narractive.tts`` entry-point group).

Quick registration::

    from examples.custom_tts_plugin import SilenceTTSEngine
    from narractive.core.narrator import register_tts_engine

    register_tts_engine(SilenceTTSEngine)

config.yaml::

    narration:
      engine: silence          # matches SilenceTTSEngine.engine_name
      silence:
        duration: 1.5          # engine-specific options (optional)

Entry-point registration (for installable packages)
---------------------------------------------------
In ``pyproject.toml``::

    [project.entry-points."narractive.tts"]
    silence = "examples.custom_tts_plugin:SilenceTTSEngine"

Narractive will auto-discover the plugin on startup.
"""

from __future__ import annotations

import logging
import struct
import wave
from pathlib import Path

from narractive.core.tts_base import TTSEngine

logger = logging.getLogger(__name__)


class SilenceTTSEngine(TTSEngine):
    """
    Minimal TTS engine that writes a silent WAV file.

    Useful for testing the pipeline without a real TTS backend.

    Config options (``narration.silence`` in ``config.yaml``):

    - ``duration`` (float, default 1.0): silence duration in seconds.
    - ``sample_rate`` (int, default 22050): audio sample rate.
    """

    engine_name = "silence"

    def generate(self, text: str, output_path: Path, lang: str = "fr", **kwargs) -> Path:
        """Write a silent WAV file whose length is proportional to *text*."""
        # Estimate 1 second per 5 words, minimum 0.5 s
        word_count = max(1, len(text.split()))
        duration = max(0.5, word_count / 5.0)

        sample_rate = 22050
        num_samples = int(sample_rate * duration)
        output_path = output_path.with_suffix(".wav")

        with wave.open(str(output_path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            # Write silence (all zeros)
            wf.writeframes(struct.pack("<" + "h" * num_samples, *([0] * num_samples)))

        logger.info(
            "[SilenceTTS] Generated %.1fs silent WAV: %s", duration, output_path.name
        )
        return output_path

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        duration = config.get("duration", 1.0)
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append(f"silence.duration must be a positive number, got: {duration!r}")
        return errors


# ---------------------------------------------------------------------------
# Self-registration when the module is imported directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Demo: register and use the engine
    from narractive.core.narrator import register_tts_engine

    register_tts_engine(SilenceTTSEngine)

    engine = SilenceTTSEngine()
    out = engine.generate(
        "Bonjour, ceci est un test de moteur TTS personnalisé.",
        Path("/tmp/test_silence.wav"),
        lang="fr",
    )
    print(f"Generated: {out}  ({out.stat().st_size} bytes)")
    print(f"Duration:  {engine.get_duration(out):.2f}s")
