"""
Production Report — Build Summary for Narractive
==================================================
Scans an output directory and generates a structured report of the
production artefacts: clip durations, narration lengths, subtitle coverage,
final video metadata, and total sizes.

Used by the ``narractive report [build_dir]`` CLI command.

Usage::

    from video_automation.core.report import ProductionReport

    rpt = ProductionReport(config, build_dir=Path("output"))
    rpt.collect()
    rpt.print_table()               # Rich table or ASCII fallback
    data = rpt.to_dict()            # Machine-readable dict
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _ffprobe_file(path: Path) -> dict:
    """
    Run ``ffprobe`` on *path* and return a metadata dict.

    Keys: ``duration`` (float, s), ``size`` (int, bytes),
          ``width`` (int), ``height`` (int), ``codec_video`` (str),
          ``codec_audio`` (str).
    Returns an empty dict when ffprobe is unavailable or fails.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                str(path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return {}
        data = json.loads(result.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

        return {
            "duration": float(fmt.get("duration", 0)),
            "size": int(fmt.get("size", 0)),
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "codec_video": video_stream.get("codec_name", ""),
            "codec_audio": audio_stream.get("codec_name", ""),
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("ffprobe failed on %s: %s", path, exc)
        return {}


def _mutagen_duration(path: Path) -> float:
    """Return audio duration in seconds via mutagen, or 0.0 on failure."""
    try:
        from mutagen import File as MutagenFile  # type: ignore

        audio = MutagenFile(str(path))
        if audio is not None and audio.info is not None:
            return float(audio.info.length)
    except Exception:  # noqa: BLE001
        pass
    return _ffprobe_file(path).get("duration", 0.0)


def _fmt_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if size_bytes <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"


def _fmt_duration(secs: float) -> str:
    """Format seconds as ``Xm Ys``."""
    secs = max(0.0, secs)
    m, s = divmod(int(secs), 60)
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


# ---------------------------------------------------------------------------
# Sequence entry
# ---------------------------------------------------------------------------


class SequenceEntry:
    """Metadata for a single sequence in the production."""

    def __init__(self, seq_id: str) -> None:
        self.seq_id = seq_id
        self.clip_path: Optional[Path] = None
        self.clip_duration: float = 0.0
        self.narration_path: Optional[Path] = None
        self.narration_duration: float = 0.0
        self.subtitles: dict[str, Path] = {}  # lang -> .srt path

    def to_dict(self) -> dict:
        return {
            "seq_id": self.seq_id,
            "clip": str(self.clip_path) if self.clip_path else None,
            "clip_duration": round(self.clip_duration, 2),
            "narration": str(self.narration_path) if self.narration_path else None,
            "narration_duration": round(self.narration_duration, 2),
            "subtitles": {lang: str(p) for lang, p in self.subtitles.items()},
        }


# ---------------------------------------------------------------------------
# Main report class
# ---------------------------------------------------------------------------


class ProductionReport:
    """
    Gathers and formats a production summary.

    Parameters
    ----------
    config : dict
        The full narractive config dict.
    build_dir : Path | None
        Root output directory.  Defaults to ``output/`` relative to cwd.
    """

    def __init__(self, config: dict, build_dir: Optional[Path] = None) -> None:
        self.config = config
        self.build_dir = Path(build_dir) if build_dir else Path(
            config.get("output", {}).get("final_dir", "output/final")
        ).parent

        # Derived directories
        out_cfg = config.get("output", {})
        narr_cfg = config.get("narration", {})
        sub_cfg = config.get("subtitles", {})
        lang_cfg = config.get("languages", {})

        self.clips_dir = Path(out_cfg.get("clips_dir", self.build_dir / "obs"))
        self.narration_dir = Path(narr_cfg.get("output_dir", self.build_dir / "narration"))
        self.final_dir = Path(out_cfg.get("final_dir", self.build_dir / "final"))

        sub_template = sub_cfg.get("output_dir", str(self.build_dir / "{lang}" / "subtitles"))
        self.subtitle_template: str = sub_template
        self.languages: list[str] = list(lang_cfg.keys()) if lang_cfg else []

        self.tts_engine: str = narr_cfg.get("engine", "edge-tts")

        self.sequences: list[SequenceEntry] = []
        self.final_video_info: dict = {}
        self.final_video_path: Optional[Path] = None
        self.generated_at: str = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def collect(
        self,
        seq_ids: Optional[list[str]] = None,
        project_name: str = "Production",
        video: Optional[str] = None,
    ) -> None:
        """
        Scan the output directories and populate report data.

        Parameters
        ----------
        seq_ids : list[str] | None
            Ordered list of sequence IDs.  When ``None``, auto-detected from
            files on disk.
        project_name : str
            Project display name (used in headings).
        video : str | None
            Video script key (e.g. ``"v01"``) used to locate narration files
            in sub-directories.
        """
        self.project_name = project_name
        self.video = video

        narr_dir = self.narration_dir
        if video:
            narr_dir = narr_dir / video

        # Auto-detect languages from subtitle directories if not in config
        languages = list(self.languages)
        if not languages:
            languages = self._detect_languages(narr_dir)

        # Auto-detect sequence IDs from narration files if not provided
        if seq_ids is None:
            seq_ids = self._detect_seq_ids(narr_dir)

        entries: list[SequenceEntry] = []
        for seq_id in seq_ids:
            entry = SequenceEntry(seq_id)

            # Clips
            clip = self._find_clip(seq_id)
            if clip:
                entry.clip_path = clip
                info = _ffprobe_file(clip)
                entry.clip_duration = info.get("duration", 0.0)

            # Narration
            narr = narr_dir / f"{seq_id}_narration.mp3"
            if not narr.exists():
                narr = narr_dir / f"{seq_id}_narration.wav"
            if narr.exists():
                entry.narration_path = narr
                entry.narration_duration = _mutagen_duration(narr)

            # Subtitles per language
            for lang in languages:
                srt_dir = Path(
                    self.subtitle_template.replace("{lang}", lang)
                )
                srt = srt_dir / f"{seq_id}.srt"
                if srt.exists():
                    entry.subtitles[lang] = srt

            entries.append(entry)

        self.sequences = entries
        self.languages_detected = languages

        # Final video
        self.final_video_path = self._find_final_video(project_name, video)
        if self.final_video_path:
            self.final_video_info = _ffprobe_file(self.final_video_path)

    def _detect_seq_ids(self, narr_dir: Path) -> list[str]:
        """Auto-detect sequence IDs from narration directory."""
        if not narr_dir.exists():
            return []
        ids = sorted(
            p.stem.replace("_narration", "")
            for p in narr_dir.glob("*_narration.*")
            if p.suffix in (".mp3", ".wav")
        )
        return ids

    def _detect_languages(self, narr_dir: Path) -> list[str]:
        """Try to detect languages from subtitle subdirectories."""
        if self.build_dir.exists():
            candidates = [
                d.name for d in self.build_dir.iterdir()
                if d.is_dir() and len(d.name) in (2, 5) and (d / "subtitles").exists()
            ]
            if candidates:
                return sorted(candidates)
        return []

    def _find_clip(self, seq_id: str) -> Optional[Path]:
        """Search for a recording clip for *seq_id*."""
        for ext in ("*.mkv", "*.mp4"):
            for p in self.clips_dir.glob(ext):
                if seq_id in p.name:
                    return p
        return None

    def _find_final_video(
        self, project_name: str, video: Optional[str]
    ) -> Optional[Path]:
        """Locate the final assembled video."""
        if not self.final_dir.exists():
            return None
        safe = project_name.lower().replace(" ", "_")
        pattern = f"{safe}_{video}_final.mp4" if video else f"{safe}_final.mp4"
        candidate = self.final_dir / pattern
        if candidate.exists():
            return candidate
        # Fallback: any mp4 in final_dir
        mp4s = sorted(self.final_dir.glob("*.mp4"))
        return mp4s[-1] if mp4s else None

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def print_table(self) -> None:
        """Print the report as a Rich table (or ASCII fallback)."""
        try:
            self._print_rich()
        except ImportError:
            self._print_ascii()

    def _print_rich(self) -> None:
        from rich.console import Console  # type: ignore
        from rich.table import Table  # type: ignore
        from rich import box  # type: ignore

        console = Console()

        title = f"Narractive Production Report — {getattr(self, 'project_name', 'Production')}"
        table = Table(
            title=title,
            box=box.DOUBLE_EDGE,
            show_lines=True,
            caption=f"Generated: {self.generated_at[:19].replace('T', ' ')}",
        )

        table.add_column("Seq", style="bold cyan", justify="center", no_wrap=True)
        table.add_column("Clip", justify="right")
        table.add_column("Narration", justify="right")
        table.add_column("Subtitles", justify="left")

        total_clip = 0.0
        total_narr = 0.0

        for entry in self.sequences:
            clip_s = _fmt_duration(entry.clip_duration) if entry.clip_path else "[dim]-[/dim]"
            narr_s = _fmt_duration(entry.narration_duration) if entry.narration_path else "[dim]-[/dim]"
            sub_s = "  ".join(
                f"[green]{lang}[/green]" if lang in entry.subtitles else f"[red]{lang}[/red]"
                for lang in getattr(self, "languages_detected", [])
            ) or "[dim]-[/dim]"
            table.add_row(entry.seq_id, clip_s, narr_s, sub_s)
            total_clip += entry.clip_duration
            total_narr += entry.narration_duration

        table.add_section()
        lang_line = "  ".join(
            f"[green]{lang} ok[/green]"
            if any(lang in e.subtitles for e in self.sequences)
            else f"[red]{lang} -[/red]"
            for lang in getattr(self, "languages_detected", [])
        ) or "[dim]none[/dim]"
        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold]{_fmt_duration(total_clip)}[/bold]",
            f"[bold]{_fmt_duration(total_narr)}[/bold]",
            lang_line,
        )

        console.print()
        console.print(table)
        console.print(f"  TTS engine  : {self.tts_engine}")

        if self.final_video_path:
            size_str = _fmt_size(self.final_video_info.get("size", 0))
            w = self.final_video_info.get("width", 0)
            h = self.final_video_info.get("height", 0)
            res = f"{w}x{h}" if w and h else "?"
            dur = _fmt_duration(self.final_video_info.get("duration", 0))
            console.print(
                f"  Final video : {self.final_video_path.name}"
                f"  ({size_str}, {res}, {dur})"
            )
        else:
            console.print("  Final video : [dim]not found[/dim]")
        console.print()

    def _print_ascii(self) -> None:
        """Fallback ASCII table when rich is not installed."""
        project_name = getattr(self, "project_name", "Production")
        langs = getattr(self, "languages_detected", [])
        title = f"Narractive Production Report — {project_name}"
        width = max(70, len(title) + 4)
        border = "=" * width

        print(f"\n{border}")
        print(f"  {title}")
        print(f"  Generated: {self.generated_at[:19].replace('T', ' ')}")
        print(border)
        print(f"  {'Seq':<14}  {'Clip':>8}  {'Narration':>10}  {'Subtitles'}")
        print("-" * width)

        total_clip = 0.0
        total_narr = 0.0

        for entry in self.sequences:
            clip_s = _fmt_duration(entry.clip_duration) if entry.clip_path else "-"
            narr_s = _fmt_duration(entry.narration_duration) if entry.narration_path else "-"
            sub_marks = " ".join(
                f"{lang}:ok" if lang in entry.subtitles else f"{lang}:-"
                for lang in langs
            ) or "-"
            print(f"  {entry.seq_id:<14}  {clip_s:>8}  {narr_s:>10}  {sub_marks}")
            total_clip += entry.clip_duration
            total_narr += entry.narration_duration

        print("-" * width)
        print(f"  {'TOTAL':<14}  {_fmt_duration(total_clip):>8}  {_fmt_duration(total_narr):>10}")
        print(border)
        print(f"  TTS engine : {self.tts_engine}")

        if self.final_video_path:
            size_str = _fmt_size(self.final_video_info.get("size", 0))
            w = self.final_video_info.get("width", 0)
            h = self.final_video_info.get("height", 0)
            res = f"{w}x{h}" if w and h else "?"
            dur = _fmt_duration(self.final_video_info.get("duration", 0))
            print(
                f"  Final video: {self.final_video_path.name}"
                f"  ({size_str}, {res}, {dur})"
            )
        else:
            print("  Final video: not found")
        print(border + "\n")

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a machine-readable dict (JSON-serialisable)."""
        total_clip = sum(e.clip_duration for e in self.sequences)
        total_narr = sum(e.narration_duration for e in self.sequences)
        total_size = sum(
            (e.clip_path.stat().st_size if e.clip_path and e.clip_path.exists() else 0)
            for e in self.sequences
        )
        langs = getattr(self, "languages_detected", [])

        result: dict = {
            "generated_at": self.generated_at,
            "project_name": getattr(self, "project_name", ""),
            "tts_engine": self.tts_engine,
            "languages": langs,
            "total_sequences": len(self.sequences),
            "total_clip_duration": round(total_clip, 2),
            "total_narration_duration": round(total_narr, 2),
            "total_clips_size_bytes": total_size,
            "sequences": [e.to_dict() for e in self.sequences],
        }

        if self.final_video_path:
            result["final_video"] = {
                "path": str(self.final_video_path),
                "size_bytes": self.final_video_info.get("size", 0),
                "duration": round(self.final_video_info.get("duration", 0.0), 2),
                "width": self.final_video_info.get("width", 0),
                "height": self.final_video_info.get("height", 0),
                "codec_video": self.final_video_info.get("codec_video", ""),
                "codec_audio": self.final_video_info.get("codec_audio", ""),
            }
        else:
            result["final_video"] = None

        return result
