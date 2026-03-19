"""
Subtitle Generator
==================
Generates SRT subtitle files from narration text with timing estimates
based on words-per-minute (WPM) rates per language.

Supports intelligent text wrapping by sentence boundaries, configurable
line width and line count, and per-language WPM defaults.

Usage::

    from video_automation.core.subtitles import SubtitleGenerator

    gen = SubtitleGenerator(config["subtitles"])
    gen.generate_for_sequence("seq01", narration_text, output_path, lang="fr")

    # Or use the low-level function directly:
    from video_automation.core.subtitles import generate_srt
    srt_content = generate_srt("Your narration text here.", wpm=155)
"""

from __future__ import annotations

import logging
import math
import re
import textwrap
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

#: Default words-per-minute rates by language (neural TTS voices).
DEFAULT_WPM: dict[str, int] = {
    "fr": 155,
    "en": 160,
    "pt": 150,
    "es": 155,
    "de": 145,
    "nl": 150,
    "it": 155,
}

#: Pause between paragraphs (seconds).
PARAGRAPH_PAUSE: float = 1.2

#: Short pause between subtitle blocks within a paragraph (seconds).
SEGMENT_PAUSE: float = 0.3

#: Lead-in margin before the first subtitle (seconds).
START_MARGIN: float = 0.5

#: Minimum subtitle display duration (seconds).
MIN_DURATION: float = 1.5


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def count_words(text: str) -> int:
    """Return the number of words in *text*."""
    return len(text.split())


def format_timestamp(seconds: float) -> str:
    """
    Convert seconds to an SRT timestamp string.

    Parameters
    ----------
    seconds : float
        Time in seconds.

    Returns
    -------
    str
        Formatted as ``HH:MM:SS,mmm``.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def estimate_duration(text: str, wpm: int) -> float:
    """
    Estimate the TTS reading duration of *text*.

    Parameters
    ----------
    text : str
        Text whose reading duration is estimated.
    wpm : int
        Words per minute rate.

    Returns
    -------
    float
        Duration in seconds (minimum ``MIN_DURATION``).
    """
    words = count_words(text.replace("\n", " "))
    duration = (words / wpm) * 60.0
    return max(duration, MIN_DURATION)


def split_into_subtitle_blocks(
    text: str,
    max_chars_per_line: int = 42,
    max_lines: int = 2,
) -> list[str]:
    """
    Split text into subtitle-sized blocks.

    Each block respects the character-per-line and line-count constraints.
    The algorithm splits on sentence boundaries first, then wraps long
    sentences into multi-line blocks.

    Parameters
    ----------
    text : str
        Input text (may contain newlines).
    max_chars_per_line : int
        Maximum characters per subtitle line.
    max_lines : int
        Maximum lines per subtitle block.

    Returns
    -------
    list[str]
        Subtitle blocks, each potentially containing internal newlines.
    """
    text = text.strip()
    if not text:
        return []

    # Split on sentence-ending punctuation
    sentences = re.split(r"(?<=[.!?:])[\s]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    blocks: list[str] = []
    for sentence in sentences:
        wrapped = textwrap.wrap(sentence, width=max_chars_per_line)
        if len(wrapped) <= max_lines:
            blocks.append("\n".join(wrapped))
        else:
            for i in range(0, len(wrapped), max_lines):
                chunk = wrapped[i : i + max_lines]
                blocks.append("\n".join(chunk))

    return blocks


# ---------------------------------------------------------------------------
# SRT generation
# ---------------------------------------------------------------------------


def generate_srt(
    narration_text: str,
    wpm: int,
    max_chars_per_line: int = 42,
    max_lines: int = 2,
    start_margin: float = START_MARGIN,
    paragraph_pause: float = PARAGRAPH_PAUSE,
    segment_pause: float = SEGMENT_PAUSE,
) -> str:
    """
    Generate complete SRT content from a narration text.

    The text is split into paragraphs (double newlines), each paragraph
    into subtitle blocks, and timing is estimated from the WPM rate.

    Parameters
    ----------
    narration_text : str
        Full narration text for one sequence.
    wpm : int
        Words per minute rate.
    max_chars_per_line : int
        Maximum characters per subtitle line.
    max_lines : int
        Maximum lines per subtitle block.
    start_margin : float
        Seconds before the first subtitle.
    paragraph_pause : float
        Extra pause between paragraphs (seconds).
    segment_pause : float
        Pause between blocks within a paragraph (seconds).

    Returns
    -------
    str
        Complete SRT file content.
    """
    paragraphs = re.split(r"\n\s*\n", narration_text.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    srt_entries: list[str] = []
    current_time = start_margin
    index = 1

    for para_idx, paragraph in enumerate(paragraphs):
        paragraph_clean = " ".join(paragraph.split())
        blocks = split_into_subtitle_blocks(
            paragraph_clean,
            max_chars_per_line=max_chars_per_line,
            max_lines=max_lines,
        )

        for block in blocks:
            duration = estimate_duration(block, wpm)
            start_ts = format_timestamp(current_time)
            end_ts = format_timestamp(current_time + duration)
            srt_entries.append(f"{index}\n{start_ts} --> {end_ts}\n{block}\n")
            current_time += duration + segment_pause
            index += 1

        # Extra pause between paragraphs
        if para_idx < len(paragraphs) - 1:
            current_time += paragraph_pause - segment_pause

    return "\n".join(srt_entries)


# ---------------------------------------------------------------------------
# High-level class
# ---------------------------------------------------------------------------


class SubtitleGenerator:
    """
    Generate SRT subtitle files from narration texts.

    Parameters
    ----------
    config : dict
        The ``subtitles`` section from config.yaml.  Recognised keys:

        - ``enabled`` (bool): Whether subtitles are active (default True).
        - ``max_chars_per_line`` (int): Max chars per line (default 42).
        - ``max_lines`` (int): Max lines per block (default 2).
        - ``output_dir`` (str): Template with ``{lang}`` placeholder.
    """

    def __init__(self, config: dict) -> None:
        self.enabled: bool = config.get("enabled", True)
        self.max_chars: int = config.get("max_chars_per_line", 42)
        self.max_lines: int = config.get("max_lines", 2)
        self.output_dir_template: str = config.get(
            "output_dir", "output/{lang}/subtitles"
        )

    def generate_for_sequence(
        self,
        sequence_id: str,
        narration_text: str,
        output_path: str | Path,
        lang: str = "fr",
        wpm: Optional[int] = None,
    ) -> Path:
        """
        Generate an SRT file for a single sequence.

        Parameters
        ----------
        sequence_id : str
            Identifier for the sequence (used for logging).
        narration_text : str
            Full narration text.
        output_path : str | Path
            Where to write the SRT file.
        lang : str
            Language code (used for WPM default lookup).
        wpm : int, optional
            Override the default WPM for this language.

        Returns
        -------
        Path
            Path to the generated SRT file.
        """
        output_path = Path(output_path)
        effective_wpm = wpm or DEFAULT_WPM.get(lang, 155)

        srt_content = generate_srt(
            narration_text,
            wpm=effective_wpm,
            max_chars_per_line=self.max_chars,
            max_lines=self.max_lines,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(srt_content, encoding="utf-8")

        words = count_words(narration_text)
        est = estimate_duration(narration_text.replace("\n", " "), effective_wpm)
        logger.info(
            "Generated %s (%d words, ~%.0fs at %d WPM)",
            output_path.name, words, est, effective_wpm,
        )
        return output_path

    def generate_for_language(
        self,
        narrations: dict[str, str],
        output_dir: str | Path,
        lang: str = "fr",
        wpm: Optional[int] = None,
    ) -> dict[str, Path]:
        """
        Batch-generate SRT files for all sequences of a language.

        Parameters
        ----------
        narrations : dict[str, str]
            Mapping of sequence_id → narration text.
        output_dir : str | Path
            Directory where SRT files are written.
        lang : str
            Language code.
        wpm : int, optional
            Override WPM.

        Returns
        -------
        dict[str, Path]
            Mapping of sequence_id → generated SRT path.
        """
        output_dir = Path(output_dir)
        results: dict[str, Path] = {}

        for seq_id, text in narrations.items():
            if not isinstance(text, str) or not text.strip():
                logger.debug("Skipping %s — empty text", seq_id)
                continue

            output_path = output_dir / f"{seq_id}.srt"
            self.generate_for_sequence(seq_id, text, output_path, lang=lang, wpm=wpm)
            results[seq_id] = output_path

        logger.info(
            "Generated %d SRT files for %s in %s", len(results), lang, output_dir,
        )
        return results
