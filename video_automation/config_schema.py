"""
Config Schema Validation
=========================
Pydantic v2 models for validating config.yaml.

Usage::

    from video_automation.config_schema import validate_config

    cfg = validate_config(raw_dict)   # returns NarractiveConfig or raises
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from pydantic import BaseModel, Field, ValidationError  # type: ignore

    _PYDANTIC_AVAILABLE = True
except ImportError:
    _PYDANTIC_AVAILABLE = False
    BaseModel = object  # type: ignore

    def Field(*a: object, **kw: object) -> None:  # type: ignore
        return None


# ---------------------------------------------------------------------------
# Pydantic models (only defined when pydantic is available)
# ---------------------------------------------------------------------------

if _PYDANTIC_AVAILABLE:
    from pydantic import BaseModel, Field

    class ObsConfig(BaseModel):
        host: str = "localhost"
        port: int = 4455
        password: str = ""
        output_dir: str = "~/Videos/MyProject"
        recording_format: str = "mkv"
        scenes: dict[str, str] = Field(default_factory=dict)

    class AppRegion(BaseModel):
        x: int = 0
        y: int = 0
        width: int = 0
        height: int = 0

    class AppConfig(BaseModel):
        window_title: str = ""
        panel_name: str = ""
        startup_wait: int = 5
        regions: dict[str, Any] = Field(default_factory=dict)

    class TimingConfig(BaseModel):
        click_delay: float = 0.3
        type_delay: float = 0.05
        scroll_delay: float = 0.2
        action_pause: float = 1.0
        transition_pause: float = 2.0
        mouse_move_duration: float = 0.5

    class DiagramsConfig(BaseModel):
        output_dir: str = "output/diagrams"
        width: int = 2560
        height: int = 1440
        theme: str = "dark"
        background_color: str = "#1a1a2e"
        font_family: str = "Segoe UI"

    class NarrationConfig(BaseModel):
        engine: str = "edge-tts"
        voice: str = "fr-FR-HenriNeural"
        output_dir: str = "output/narration"
        speed: str = "+0%"
        f5_ref_audio: str | None = None
        f5_ref_text: str | None = None
        f5_model: str | None = None
        f5_speed: float | None = None
        f5_conda_env: str | None = None
        f5_remove_silence: bool = False
        kokoro_lang: str | None = None
        kokoro_voice: str | None = None
        kokoro_speed: float | None = None
        kokoro_conda_env: str | None = None

    class SubtitlesConfig(BaseModel):
        enabled: bool = True
        max_chars_per_line: int = 42
        max_lines: int = 2
        output_dir: str = "output/{lang}/subtitles"

    class CaptureConfig(BaseModel):
        fps: int = 10
        output_dir: str = "output/captures"
        resolution: str = "2560x1440"
        display: str = ":99"
        method: str = "import"
        codec: str = "libx264"
        quality: int = 23
        format: str = "mp4"
        scenes: dict[str, str] = Field(default_factory=dict)

    class OutputConfig(BaseModel):
        final_dir: str = "output/final"
        resolution: str = "2560x1440"
        fps: int = 30
        codec: str = "libx264"
        quality: str = "23"

    class LanguageEntry(BaseModel):
        voice: str | None = None

    class NarractiveConfig(BaseModel):
        obs: ObsConfig = Field(default_factory=ObsConfig)
        app: AppConfig = Field(default_factory=AppConfig)
        timing: TimingConfig = Field(default_factory=TimingConfig)
        diagrams: DiagramsConfig = Field(default_factory=DiagramsConfig)
        narration: NarrationConfig = Field(default_factory=NarrationConfig)
        subtitles: SubtitlesConfig = Field(default_factory=SubtitlesConfig)
        capture: CaptureConfig = Field(default_factory=CaptureConfig)
        output: OutputConfig = Field(default_factory=OutputConfig)
        languages: dict[str, Any] = Field(default_factory=dict)

else:
    # Stubs when pydantic is not installed
    class NarractiveConfig:  # type: ignore
        pass

    class ObsConfig:  # type: ignore
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_config(raw: dict) -> Any:
    """
    Validate a raw config dict against the NarractiveConfig schema.

    Parameters
    ----------
    raw : dict
        The config as loaded from YAML.

    Returns
    -------
    NarractiveConfig
        Validated config object (if pydantic is available).
        Returns the raw dict unchanged if pydantic is not installed.

    Raises
    ------
    SystemExit
        If pydantic is available and validation fails, prints human-readable
        errors and exits with code 1.
    """
    if not _PYDANTIC_AVAILABLE:
        logger.warning(
            "pydantic not installed — config validation skipped. "
            "Install with: pip install 'narractive[config]'"
        )
        return raw

    try:
        return NarractiveConfig.model_validate(raw)
    except ValidationError as exc:
        import sys

        logger.error("Config validation failed:")
        for error in exc.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            msg = error["msg"]
            logger.error("  %s: %s", loc or "(root)", msg)
        sys.exit(1)


def is_pydantic_available() -> bool:
    """Return True if pydantic v2 is installed."""
    return _PYDANTIC_AVAILABLE


def validate_config_and_warn(cfg: dict) -> None:
    """
    Validate the config and either warn (Pydantic missing) or exit on errors.

    Called by load_config() after loading.
    """
    if not _PYDANTIC_AVAILABLE:
        logger.debug("Pydantic not available — skipping schema validation.")
        return
    # validate_config already exits on errors when pydantic is available
    validate_config(cfg)
