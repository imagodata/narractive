"""
TTS Engine Plugin Base — Abstract interface for custom TTS engines
==================================================================
Defines the :class:`TTSEngine` abstract base class that third-party TTS
engines must implement, and the :func:`register_tts_engine` /
:func:`get_tts_engine` registry functions used by :class:`~video_automation.core.narrator.Narrator`.

Quick start::

    from pathlib import Path
    from video_automation.core.tts_base import TTSEngine, register_tts_engine

    class MyEngine(TTSEngine):
        engine_name = "my-engine"

        def generate(self, text: str, output_path: Path, lang: str = "fr", **kwargs) -> Path:
            # ... write audio to output_path ...
            return output_path

    register_tts_engine(MyEngine)

Then in ``config.yaml``::

    narration:
      engine: my-engine

Entry-point registration (for installable packages)::

    [project.entry-points."narractive.tts"]
    my-engine = "my_package.tts_engine:MyEngine"

Entry-point plugins are auto-discovered when :func:`load_entry_point_plugins` is called.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type["TTSEngine"]] = {}


def register_tts_engine(engine_cls: type["TTSEngine"]) -> None:
    """
    Register a :class:`TTSEngine` subclass in the global registry.

    Parameters
    ----------
    engine_cls : type[TTSEngine]
        A class with an ``engine_name`` class attribute.

    Raises
    ------
    ValueError
        If ``engine_cls`` does not define a non-empty ``engine_name``.
    """
    name = getattr(engine_cls, "engine_name", None)
    if not name:
        raise ValueError(
            f"TTSEngine subclass {engine_cls.__name__} must define a non-empty 'engine_name'."
        )
    if name in _REGISTRY:
        logger.debug("TTS engine '%s' already registered — overwriting with %s", name, engine_cls)
    _REGISTRY[name] = engine_cls
    logger.debug("Registered TTS engine: '%s' -> %s", name, engine_cls.__name__)


def get_tts_engine(name: str) -> type["TTSEngine"] | None:
    """
    Return the registered :class:`TTSEngine` class for *name*, or ``None``.

    Parameters
    ----------
    name : str
        Engine name as declared in ``engine_cls.engine_name``.
    """
    return _REGISTRY.get(name)


def list_registered_engines() -> list[str]:
    """Return the names of all registered TTS engines (built-in + plugins)."""
    return sorted(_REGISTRY.keys())


def load_entry_point_plugins() -> None:
    """
    Discover and register TTS engine plugins declared via ``narractive.tts``
    entry points.

    Call this once at startup (it is a no-op if ``importlib.metadata`` is
    unavailable or no plugins are installed).
    """
    try:
        from importlib.metadata import entry_points

        eps = entry_points(group="narractive.tts")
        for ep in eps:
            try:
                engine_cls = ep.load()
                register_tts_engine(engine_cls)
                logger.info("Loaded TTS plugin from entry point '%s': %s", ep.name, engine_cls)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load TTS plugin '%s': %s", ep.name, exc)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Entry-point plugin discovery skipped: %s", exc)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class TTSEngine(ABC):
    """
    Abstract base class for TTS engine plugins.

    Subclasses must:

    1. Set a unique ``engine_name`` class attribute (string).
    2. Implement :meth:`generate`.

    Optionally override :meth:`get_duration` for format-specific duration
    probing (the default implementation uses ``mutagen`` or ``ffprobe``).

    Example::

        class ElevenLabsV3Engine(TTSEngine):
            engine_name = "elevenlabs-v3"

            def generate(self, text, output_path, lang="fr", **kwargs):
                ...
                return output_path
    """

    #: Unique engine identifier used in ``config.yaml`` (``narration.engine``).
    engine_name: str = ""

    @abstractmethod
    def generate(self, text: str, output_path: Path, lang: str = "fr", **kwargs) -> Path:
        """
        Synthesise *text* and write the audio to *output_path*.

        Parameters
        ----------
        text : str
            Narration text to synthesise.
        output_path : Path
            Destination file.  The parent directory is guaranteed to exist.
        lang : str
            BCP 47 language code (e.g. ``"fr"``, ``"en"``, ``"pt"``).
        **kwargs
            Additional engine-specific keyword arguments forwarded from the
            ``narration.<engine_name>`` config section.

        Returns
        -------
        Path
            Absolute path to the generated audio file (usually *output_path*).
        """
        ...  # pragma: no cover

    def get_duration(self, audio_path: Path) -> float:
        """
        Return the duration of *audio_path* in seconds.

        The default implementation tries ``mutagen`` first, then ``ffprobe``.
        Override for engines that produce formats not supported by mutagen.

        Parameters
        ----------
        audio_path : Path
            Path to the audio file.

        Returns
        -------
        float
            Duration in seconds, or ``0.0`` on failure.
        """
        try:
            from mutagen import File as MutagenFile  # type: ignore

            audio = MutagenFile(str(audio_path))
            if audio is not None and audio.info is not None:
                return float(audio.info.length)
        except Exception:  # noqa: BLE001
            pass

        # Fallback: ffprobe
        return _ffprobe_duration(audio_path)

    def validate_config(self, config: dict) -> list[str]:
        """
        Validate the engine-specific config section.

        Override to add custom validation.  Return a list of error strings
        (empty list = valid).

        Parameters
        ----------
        config : dict
            The ``narration.<engine_name>`` section from config.yaml.

        Returns
        -------
        list[str]
            List of validation error messages (empty = valid).
        """
        return []


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _ffprobe_duration(audio_path: Path) -> float:
    """Return audio duration via ffprobe, or 0.0 on failure."""
    import json
    import subprocess

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0))
    except Exception:  # noqa: BLE001
        pass
    return 0.0
