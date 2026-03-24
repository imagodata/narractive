"""
Video Assembler
===============
Post-production pipeline: combines OBS recordings, diagram overlays,
narration audio, and subtitles into the final video using FFmpeg.

Supports quality presets (draft/final), subtitle burning (ASS/libass),
intro/outro generation from images, and duration matching.

Requires FFmpeg on PATH.

Usage:
    from narractive.core.video_assembler import VideoAssembler
    va = VideoAssembler(config["output"])
    va.remux_mkv_to_mp4("raw_recording.mkv")
    va.assemble_sequence("seq01", "fr", base_dir, config)
    va.create_final_video(clips, narrations, diagrams, "output/final/video.mp4")
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Quality presets
# ---------------------------------------------------------------------------

QUALITY_PRESETS: dict[str, dict] = {
    "draft": {
        "preset": "ultrafast",
        "crf": 28,
        "description": "Fast encoding for preview",
    },
    "final": {
        "preset": "slow",
        "crf": 18,
        "description": "High quality for publication",
    },
}

# Default intro/outro duration when generating from images
INTRO_DURATION = 4.0
OUTRO_DURATION = 4.0

# Audio output settings
AUDIO_SAMPLE_RATE = 44100
AUDIO_CHANNELS = 2


def _check_ffmpeg() -> None:
    """Raise RuntimeError if FFmpeg is not available on PATH."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "FFmpeg not found on PATH. "
            "Install from https://ffmpeg.org/download.html and add to PATH."
        )


def _run_ffmpeg(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run an FFmpeg command and return the result."""
    cmd = ["ffmpeg", "-y", *args]
    logger.debug("FFmpeg command: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and result.returncode != 0:
        logger.error("FFmpeg stderr:\n%s", result.stderr[-3000:])
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result


class VideoAssembler:
    """
    Handles all FFmpeg-based post-production operations.

    Parameters
    ----------
    config : dict
        The 'output' section from config.yaml.
    """

    def __init__(self, config: dict) -> None:
        self.final_dir = Path(config.get("final_dir", "output/final"))
        self.resolution: str = config.get("resolution", "1920x1080")
        self.fps: int = config.get("fps", 30)
        self.codec: str = config.get("codec", "libx264")
        self.quality: str = str(config.get("quality", "23"))
        self.final_dir.mkdir(parents=True, exist_ok=True)
        _check_ffmpeg()

    # ------------------------------------------------------------------
    # Remux
    # ------------------------------------------------------------------

    def remux_mkv_to_mp4(self, mkv_path: str | Path, output_path: Optional[str | Path] = None) -> Path:
        """
        Losslessly remux an MKV to MP4 (no re-encoding).

        Parameters
        ----------
        mkv_path : str | Path
            Input MKV file.
        output_path : str | Path, optional
            Output MP4 path. Defaults to same location with .mp4 extension.

        Returns
        -------
        Path
            Path to the MP4 file.
        """
        mkv_path = Path(mkv_path)
        if output_path is None:
            output_path = mkv_path.with_suffix(".mp4")
        output_path = Path(output_path)

        _run_ffmpeg(
            "-i", str(mkv_path),
            "-c", "copy",
            str(output_path),
        )
        logger.info("Remuxed %s → %s", mkv_path.name, output_path.name)
        return output_path

    # ------------------------------------------------------------------
    # Narration
    # ------------------------------------------------------------------

    def add_narration(
        self,
        video_path: str | Path,
        narration_path: str | Path,
        output_path: str | Path,
        narration_volume: float = 1.0,
        original_volume: float = 0.3,
    ) -> Path:
        """
        Mix narration audio into the video, reducing original audio level.

        Parameters
        ----------
        video_path : str | Path
            Input video file.
        narration_path : str | Path
            Narration audio file (MP3 or WAV).
        output_path : str | Path
            Output video file.
        narration_volume : float
            Volume multiplier for narration (0.0–2.0).
        original_volume : float
            Volume multiplier for original video audio (0 = mute original).

        Returns
        -------
        Path
            Path to the output file.
        """
        video_path = Path(video_path)
        narration_path = Path(narration_path)
        output_path = Path(output_path)

        filter_complex = (
            f"[0:a]volume={original_volume}[orig];"
            f"[1:a]volume={narration_volume}[narr];"
            "[orig][narr]amix=inputs=2:duration=first:dropout_transition=3:normalize=0[aout]"
        )

        _run_ffmpeg(
            "-i", str(video_path),
            "-i", str(narration_path),
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path),
        )
        logger.info("Added narration to %s → %s", video_path.name, output_path.name)
        return output_path

    # ------------------------------------------------------------------
    # Diagram overlay
    # ------------------------------------------------------------------

    def combine_recording_with_diagrams(
        self,
        recording_path: str | Path,
        diagram_paths: list[str | Path],
        timestamps: list[float],
        output_path: str | Path,
        diagram_duration: float = 5.0,
        fade_duration: float = 0.5,
    ) -> Path:
        """
        Overlay diagram images onto the recording at specified timestamps.

        Each diagram is faded in and out as a picture-in-picture overlay.

        Parameters
        ----------
        recording_path : str | Path
            Main recording video.
        diagram_paths : list
            List of PNG image paths (one per timestamp).
        timestamps : list[float]
            Start times (seconds) for each diagram overlay.
        output_path : str | Path
            Output video file.
        diagram_duration : float
            How long each diagram stays on screen.
        fade_duration : float
            Fade in/out duration.

        Returns
        -------
        Path
        """
        recording_path = Path(recording_path)
        output_path = Path(output_path)

        if len(diagram_paths) != len(timestamps):
            raise ValueError("diagram_paths and timestamps must have the same length.")

        if not diagram_paths:
            logger.info("No diagrams to overlay; copying source.")
            shutil.copy2(recording_path, output_path)
            return output_path

        # Build FFmpeg filter_complex for each overlay
        inputs = ["-i", str(recording_path)]
        for dp in diagram_paths:
            inputs += ["-i", str(dp)]

        # Chain overlays
        filter_parts: list[str] = []
        prev_label = "0:v"
        for idx, (dp, ts) in enumerate(zip(diagram_paths, timestamps), start=1):
            fade_in = (
                f"[{idx}:v]"
                f"fade=t=in:st=0:d={fade_duration},"
                f"fade=t=out:st={diagram_duration - fade_duration}:d={fade_duration}[diag{idx}]"
            )
            overlay = (
                f"[{prev_label}][diag{idx}]"
                f"overlay=x=(W-w)/2:y=(H-h)/2:enable='between(t,{ts},{ts + diagram_duration})'[v{idx}]"
            )
            filter_parts.append(fade_in)
            filter_parts.append(overlay)
            prev_label = f"v{idx}"

        filter_complex = ";".join(filter_parts)

        _run_ffmpeg(
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{prev_label}]",
            "-map", "0:a?",
            "-c:v", self.codec,
            "-crf", self.quality,
            "-c:a", "copy",
            str(output_path),
        )
        logger.info("Combined recording with %d diagrams → %s", len(diagram_paths), output_path.name)
        return output_path

    # ------------------------------------------------------------------
    # Chapter markers
    # ------------------------------------------------------------------

    def add_chapter_markers(
        self,
        video_path: str | Path,
        chapters: list[dict],
        output_path: str | Path,
    ) -> Path:
        """
        Embed chapter markers into an MP4 file as FFMETADATA chapters.

        Each chapter is a dict with at minimum a ``title`` key and a
        ``start`` key (start time in seconds).  An optional ``end`` key may
        be supplied; if absent it defaults to the start of the next chapter
        (or the total video duration for the last chapter).

        Parameters
        ----------
        video_path : str | Path
            Input MP4 file.
        chapters : list[dict]
            Ordered list of chapter descriptors, e.g.::

                [
                    {"title": "Introduction", "start": 0.0},
                    {"title": "Demo",         "start": 30.5},
                    {"title": "Conclusion",   "start": 90.0},
                ]

        output_path : str | Path
            Output MP4 file with chapter metadata.

        Returns
        -------
        Path
            Path to the output file.

        Raises
        ------
        ValueError
            If *chapters* is empty.
        """
        video_path = Path(video_path)
        output_path = Path(output_path)

        if not chapters:
            raise ValueError("chapters list must not be empty.")

        # Determine total video duration for closing the last chapter
        total_duration = get_media_duration(video_path) or 0.0

        # Build FFMETADATA content
        meta_lines = [";FFMETADATA1\n"]
        for i, chapter in enumerate(chapters):
            start_sec = float(chapter["start"])
            if "end" in chapter:
                end_sec = float(chapter["end"])
            elif i + 1 < len(chapters):
                end_sec = float(chapters[i + 1]["start"])
            else:
                end_sec = total_duration

            # FFmpeg chapters use millisecond timebase by convention
            start_ms = int(start_sec * 1000)
            end_ms = int(end_sec * 1000)
            title = chapter.get("title", f"Chapter {i + 1}")

            meta_lines.append("[CHAPTER]")
            meta_lines.append("TIMEBASE=1/1000")
            meta_lines.append(f"START={start_ms}")
            meta_lines.append(f"END={end_ms}")
            meta_lines.append(f"title={title}")
            meta_lines.append("")

        metadata_content = "\n".join(meta_lines)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(metadata_content)
            meta_file = tmp.name

        try:
            _run_ffmpeg(
                "-i", str(video_path),
                "-i", meta_file,
                "-map_metadata", "1",
                "-map_chapters", "1",
                "-c", "copy",
                str(output_path),
            )
        finally:
            Path(meta_file).unlink(missing_ok=True)

        logger.info(
            "Added %d chapter markers to %s → %s",
            len(chapters), video_path.name, output_path.name,
        )
        return output_path

    # ------------------------------------------------------------------
    # Intro / Outro
    # ------------------------------------------------------------------

    #: Video file extensions treated as clip sources (not images)
    VIDEO_EXTENSIONS: frozenset[str] = frozenset(
        {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".m4v"}
    )

    def add_intro_outro(
        self,
        video_path: str | Path,
        intro_path: Optional[str | Path],
        outro_path: Optional[str | Path],
        output_path: str | Path,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        quality: str = "draft",
    ) -> Path:
        """
        Concatenate intro + main video + outro.

        Both image files (``.png``, ``.jpg``, …) and video clips
        (``.mp4``, ``.mov``, ``.avi``, …) are accepted as intro/outro
        sources.  Image sources are first converted to a short video clip
        via :meth:`create_image_clip`; video clips are used directly.

        Parameters
        ----------
        video_path : str | Path
            Main video clip.
        intro_path : str | Path, optional
            Intro image or video clip.
        outro_path : str | Path, optional
            Outro image or video clip.
        output_path : str | Path
            Final output.
        width, height : int
            Resolution used when converting images to clips.
        fps : int
            Frame rate used when converting images to clips.
        quality : str
            Encoding preset (``"draft"`` or ``"final"``) for image clips.

        Returns
        -------
        Path
        """
        output_path = Path(output_path)

        def _resolve_clip(
            src: Optional[str | Path], role: str
        ) -> Optional[Path]:
            """Return a ready-to-concatenate video clip path, or None."""
            if src is None:
                return None
            src = Path(src)
            if not src.exists():
                logger.debug("%s not found, skipping: %s", role, src)
                return None
            if src.suffix.lower() in self.VIDEO_EXTENSIONS:
                # Already a video — use directly
                return src
            # Assume image — convert to a video clip
            clip_path = output_path.parent / f"_{role}_{src.stem}_clip.mp4"
            logger.info("Converting %s image to video clip: %s", role, src.name)
            self.create_image_clip(
                src, clip_path,
                duration=INTRO_DURATION if role == "intro" else OUTRO_DURATION,
                width=width, height=height, fps=fps, quality=quality,
            )
            return clip_path

        clips: list[Path] = []
        intro_clip = _resolve_clip(intro_path, "intro")
        if intro_clip:
            clips.append(intro_clip)
        clips.append(Path(video_path))
        outro_clip = _resolve_clip(outro_path, "outro")
        if outro_clip:
            clips.append(outro_clip)

        if len(clips) == 1:
            shutil.copy2(clips[0], output_path)
            return output_path

        # Concatenate via FFmpeg concat demuxer
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            for clip in clips:
                tmp.write(f"file '{clip.resolve()}'\n")
            concat_file = tmp.name

        _run_ffmpeg(
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            str(output_path),
        )
        Path(concat_file).unlink(missing_ok=True)
        logger.info("Concatenated %d clips → %s", len(clips), output_path.name)
        return output_path

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def create_final_video(
        self,
        clips: list[str | Path],
        narrations: list[str | Path],
        diagrams: Optional[dict] = None,
        output_path: Optional[str | Path] = None,
    ) -> Path:
        """
        Full post-production pipeline:
        1. Concatenate all sequence clips.
        2. Mix narration audio.
        3. Encode final video.

        Parameters
        ----------
        clips : list
            Ordered list of video clip files (one per sequence).
        narrations : list
            Ordered list of narration audio files (matched to clips).
        diagrams : dict, optional
            Mapping of {timestamp: png_path} for diagram overlays (optional).
        output_path : str | Path, optional
            Final output path.

        Returns
        -------
        Path
        """
        if output_path is None:
            output_path = self.final_dir / "filtermate_final.mp4"
        output_path = Path(output_path)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Step 1: Concatenate all clips
            logger.info("Step 1/3: Concatenating %d clips…", len(clips))
            concat_path = tmp / "concatenated.mp4"
            if len(clips) == 1:
                shutil.copy2(clips[0], concat_path)
            else:
                self._concat_clips(clips, concat_path)

            # Step 2: Add narrations
            logger.info("Step 2/3: Mixing %d narration tracks…", len(narrations))
            if narrations:
                # Concatenate all narration audio first
                narr_concat = tmp / "narration_concat.mp3"
                self._concat_audio(narrations, narr_concat)
                narrated_path = tmp / "with_narration.mp4"
                self.add_narration(concat_path, narr_concat, narrated_path)
            else:
                narrated_path = concat_path

            # Step 3: Final encode
            logger.info("Step 3/3: Final encoding → %s", output_path.name)
            _run_ffmpeg(
                "-i", str(narrated_path),
                "-c:v", self.codec,
                "-crf", self.quality,
                "-preset", "slow",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                "-vf", f"scale={self.resolution.replace('x', ':')}",
                "-r", str(self.fps),
                str(output_path),
            )

        logger.info("Final video created: %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # Timecode-based assembly (from TimelineSequence)
    # ------------------------------------------------------------------

    def create_final_video_with_timecodes(
        self,
        clips: list[str | Path],
        timeline_results: list,
        output_path: str | Path | None = None,
    ) -> Path:
        """
        Full post-production with precise narration timecodes.

        Each clip has an associated TimelineResult (or None for legacy
        sequences).  Narration segments are placed at their exact recorded
        timecodes in the final audio track.

        Parameters
        ----------
        clips : list
            Ordered list of video clip files (one per sequence).
        timeline_results : list
            List of TimelineResult objects (or None) matching each clip.
        output_path : str | Path, optional
            Final output path.
        """
        if output_path is None:
            output_path = self.final_dir / "filtermate_final.mp4"
        output_path = Path(output_path)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Step 1: Concatenate all video clips
            logger.info("Step 1/4: Concatenating %d clips…", len(clips))
            concat_path = tmp / "concatenated.mp4"
            if len(clips) == 1:
                shutil.copy2(clips[0], concat_path)
            else:
                self._concat_clips(clips, concat_path)

            # Step 2: Get clip durations to compute absolute timecodes
            logger.info("Step 2/4: Computing narration timecodes…")
            clip_offsets = self._get_clip_offsets(clips)

            # Step 3: Build narration track with precise timecodes
            logger.info("Step 3/4: Building narration track…")
            narr_track = tmp / "narration_timed.wav"
            has_narration = self._build_timed_narration_track(
                clip_offsets, timeline_results, narr_track,
            )

            # Step 4: Mix narration with video and encode
            if has_narration:
                logger.info("Step 4/4: Mixing narration + final encode…")
                narrated_path = tmp / "with_narration.mp4"
                self.add_narration(concat_path, narr_track, narrated_path)
            else:
                narrated_path = concat_path

            _run_ffmpeg(
                "-i", str(narrated_path),
                "-c:v", self.codec,
                "-crf", self.quality,
                "-preset", "slow",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                "-vf", f"scale={self.resolution.replace('x', ':')}",
                "-r", str(self.fps),
                str(output_path),
            )

        logger.info("Final video (timecode-based) created: %s", output_path)
        return output_path

    def _get_clip_offsets(self, clips: list[str | Path]) -> list[float]:
        """
        Return cumulative start offsets for each clip.

        E.g., if clip durations are [10.0, 15.0, 20.0],
        offsets are [0.0, 10.0, 25.0].
        """
        import json

        offsets: list[float] = [0.0]
        for clip in clips[:-1]:
            try:
                result = subprocess.run(
                    [
                        "ffprobe", "-v", "quiet",
                        "-print_format", "json",
                        "-show_format",
                        str(clip),
                    ],
                    capture_output=True, text=True, check=True,
                )
                data = json.loads(result.stdout)
                duration = float(data["format"]["duration"])
            except Exception as exc:
                logger.warning("Could not get duration for %s: %s", clip, exc)
                duration = 30.0  # fallback
            offsets.append(offsets[-1] + duration)
        return offsets

    def _build_timed_narration_track(
        self,
        clip_offsets: list[float],
        timeline_results: list,
        output_path: Path,
    ) -> bool:
        """
        Build a single narration audio track with segments placed at
        their exact timecodes using FFmpeg adelay filter.

        Returns True if any narration segments were placed.
        """
        # Collect all (absolute_timecode, audio_path) pairs
        all_segments: list[tuple[float, Path]] = []

        for i, tl_result in enumerate(timeline_results):
            if tl_result is None:
                continue
            clip_offset = clip_offsets[i] if i < len(clip_offsets) else 0.0
            for rel_timecode, audio_path in tl_result.narration_timecodes:
                abs_timecode = clip_offset + rel_timecode
                all_segments.append((abs_timecode, audio_path))
                logger.debug(
                    "Narration segment at %.1fs: %s", abs_timecode, audio_path.name,
                )

        if not all_segments:
            return False

        logger.info("Placing %d narration segments with timecodes", len(all_segments))

        # Get total video duration for the silent base track
        total_duration = clip_offsets[-1] + 60.0 if clip_offsets else 300.0

        # Build FFmpeg filter: create silent base, overlay each segment with adelay
        inputs = []
        filter_parts = []

        # Input 0: silent base track
        inputs.extend([
            "-f", "lavfi",
            "-t", str(total_duration),
            "-i", f"anullsrc=r=44100:cl=stereo",
        ])

        # Filter out empty or missing narration files
        valid_segments: list[tuple[float, Path]] = []
        for timecode, audio_path in all_segments:
            if not audio_path.exists() or audio_path.stat().st_size == 0:
                logger.warning("Skipping invalid narration segment: %s", audio_path.name)
                continue
            valid_segments.append((timecode, audio_path))

        if not valid_segments:
            return False

        all_segments = valid_segments
        logger.info("Placing %d valid narration segments", len(all_segments))

        # Add each narration segment as an input
        for idx, (timecode, audio_path) in enumerate(all_segments):
            input_idx = idx + 1
            inputs.extend(["-i", str(audio_path)])
            delay_ms = int(timecode * 1000)
            filter_parts.append(
                f"[{input_idx}:a]adelay={delay_ms}|{delay_ms}[seg{idx}]"
            )

        # Mix all delayed segments with the silent base.
        # normalize=0 prevents amix from dividing volume by N inputs
        # (otherwise narration becomes inaudible with many segments).
        mix_inputs = "[0:a]" + "".join(f"[seg{i}]" for i in range(len(all_segments)))
        filter_parts.append(
            f"{mix_inputs}amix=inputs={len(all_segments) + 1}:"
            f"duration=first:dropout_transition=0:normalize=0[aout]"
        )

        filter_complex = ";".join(filter_parts)

        _run_ffmpeg(
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            "-c:a", "pcm_s16le",
            str(output_path),
        )

        logger.info("Timed narration track created: %s", output_path.name)
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _concat_clips(self, clips: list[str | Path], output_path: Path) -> None:
        """Concatenate video clips via FFmpeg concat demuxer."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            for clip in clips:
                tmp.write(f"file '{Path(clip).resolve()}'\n")
            concat_file = tmp.name
        _run_ffmpeg(
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            str(output_path),
        )
        Path(concat_file).unlink(missing_ok=True)

    def _concat_audio(self, audio_files: list[str | Path], output_path: Path) -> None:
        """Concatenate audio files into a single track."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            for af in audio_files:
                tmp.write(f"file '{Path(af).resolve()}'\n")
            concat_file = tmp.name
        _run_ffmpeg(
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            str(output_path),
        )
        Path(concat_file).unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Per-sequence assembly (recording + narration + subtitles)
    # ------------------------------------------------------------------

    def assemble_sequence(
        self,
        sequence_id: str,
        lang: str,
        base_dir: str | Path,
        config: dict,
        quality: str = "draft",
        burn_subtitles: bool = True,
        dry_run: bool = False,
    ) -> Optional[Path]:
        """
        Assemble a single sequence: recording + narration + subtitles.

        Looks for files in the standard directory layout::

            output/{lang}/recordings/{sequence_id}.mp4
            output/{lang}/narrations/{sequence_id}.wav
            output/{lang}/subtitles/{sequence_id}.srt
            output/{lang}/captures/intro.png  (optional)
            output/{lang}/captures/outro.png  (optional)

        Parameters
        ----------
        sequence_id : str
            Sequence identifier (e.g. ``"a1_intro"``).
        lang : str
            Language code (e.g. ``"fr"``).
        base_dir : str | Path
            Project base directory containing ``output/``.
        config : dict
            Full project configuration.
        quality : str
            Encoding preset: ``"draft"`` or ``"final"``.
        burn_subtitles : bool
            If True, burn SRT subtitles into the video.
        dry_run : bool
            If True, log commands without executing.

        Returns
        -------
        Path or None
            Path to the assembled video, or None on failure.
        """
        base_dir = Path(base_dir)
        obs_cfg = config.get("obs", {})
        narr_cfg = config.get("narration", {})
        sub_cfg = config.get("subtitles", {})
        out_cfg = config.get("output", {})
        cap_cfg = config.get("capture", {})

        def _resolve(template: str) -> Path:
            return base_dir / template.replace("{lang}", lang)

        rec_dir = _resolve(obs_cfg.get("output_dir", f"output/{lang}/recordings"))
        narr_dir = _resolve(narr_cfg.get("output_dir", f"output/{lang}/narrations"))
        sub_dir = _resolve(sub_cfg.get("output_dir", f"output/{lang}/subtitles"))
        cap_dir = _resolve(cap_cfg.get("output_dir", f"output/{lang}/captures"))
        final_dir = _resolve(out_cfg.get("final_dir", f"output/{lang}/final"))

        recording = rec_dir / f"{sequence_id}.mp4"
        narration = narr_dir / f"{sequence_id}.wav"
        subtitle = sub_dir / f"{sequence_id}.srt"
        intro_img = cap_dir / "intro.png"
        outro_img = cap_dir / "outro.png"
        output = final_dir / f"{sequence_id}.mp4"

        # Check required files
        if not recording.exists():
            logger.warning("Recording missing: %s", recording)
            return None
        if not narration.exists():
            logger.warning("Narration missing: %s", narration)
            return None

        has_subs = burn_subtitles and subtitle.exists()
        has_intro = intro_img.exists()
        has_outro = outro_img.exists()

        # Get durations
        video_dur = get_media_duration(recording)
        audio_dur = get_media_duration(narration)
        if video_dur is None or audio_dur is None:
            if not dry_run:
                logger.error("Cannot read media durations")
                return None
            video_dur = video_dur or 60.0
            audio_dur = audio_dur or 60.0

        # Encoding preset
        preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["draft"])
        resolution = out_cfg.get("resolution", "1920x1080")
        width, height = resolution.split("x")
        fps = out_cfg.get("fps", 30)

        if not dry_run:
            final_dir.mkdir(parents=True, exist_ok=True)

        # Build filter_complex
        filter_parts: list[str] = []

        # Scale + fps
        filter_parts.append(
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"fps={fps},setsar=1[v_scaled]"
        )

        # Duration matching
        if audio_dur > video_dur:
            pad = audio_dur - video_dur
            filter_parts.append(
                f"[v_scaled]tpad=stop_mode=clone:stop_duration={pad:.3f}[v_padded]"
            )
        else:
            filter_parts.append(
                f"[v_scaled]trim=0:{audio_dur:.3f},setpts=PTS-STARTPTS[v_padded]"
            )
        current_v = "[v_padded]"

        # Subtitle burn
        if has_subs:
            srt_escaped = str(subtitle).replace("\\", "/").replace(":", "\\:")
            sub_font = sub_cfg.get("font", "Arial")
            sub_size = sub_cfg.get("font_size", 24)
            pos = sub_cfg.get("position", "bottom")
            alignment = 2 if pos == "bottom" else 6
            force_style = (
                f"FontName={sub_font},FontSize={sub_size},"
                f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                f"BorderStyle=3,Outline=2,Shadow=1,"
                f"Alignment={alignment},MarginV=30"
            )
            filter_parts.append(
                f"{current_v}subtitles='{srt_escaped}':force_style='{force_style}'[v_sub]"
            )
            current_v = "[v_sub]"

        # Audio resample
        filter_parts.append(
            f"[1:a]aresample={AUDIO_SAMPLE_RATE},"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo[a_out]"
        )

        # Final video label
        if current_v != "[v_out]":
            filter_parts.append(f"{current_v}null[v_out]")

        filter_complex = ";\n".join(filter_parts)

        # Build FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-i", str(recording),
            "-i", str(narration),
            "-filter_complex", filter_complex,
            "-map", "[v_out]",
            "-map", "[a_out]",
            "-c:v", "libx264",
            "-preset", preset["preset"],
            "-crf", str(preset["crf"]),
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", str(AUDIO_SAMPLE_RATE),
            "-ac", str(AUDIO_CHANNELS),
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            str(output),
        ]

        if dry_run:
            logger.info("[DRY-RUN] %s", " ".join(str(c) for c in cmd))
            return output

        logger.info("Assembling %s (%s)…", sequence_id, quality)
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=600,
        )
        if result.returncode != 0:
            logger.error("FFmpeg failed:\n%s", result.stderr[-2000:])
            return None

        if output.exists():
            dur = get_media_duration(output)
            size = output.stat().st_size
            logger.info(
                "Assembled %s — %s, %.1f MB",
                output.name,
                format_duration(dur) if dur else "?",
                size / (1024 * 1024),
            )
        return output

    @staticmethod
    def create_image_clip(
        image_path: str | Path,
        output_path: str | Path,
        duration: float = 4.0,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        quality: str = "draft",
    ) -> Path:
        """
        Generate a video clip from a static image (for intro/outro).

        Parameters
        ----------
        image_path : str | Path
            Input PNG/JPG image.
        output_path : str | Path
            Output MP4 path.
        duration : float
            Clip duration in seconds.
        width, height : int
            Video resolution.
        fps : int
            Frame rate.
        quality : str
            Encoding preset name.

        Returns
        -------
        Path
            Path to the generated clip.
        """
        preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["draft"])
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        _run_ffmpeg(
            "-loop", "1",
            "-i", str(image_path),
            "-f", "lavfi",
            "-i", f"anullsrc=r={AUDIO_SAMPLE_RATE}:cl=stereo",
            "-t", f"{duration:.3f}",
            "-vf", (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"fps={fps},setsar=1"
            ),
            "-c:v", "libx264",
            "-preset", preset["preset"],
            "-crf", str(preset["crf"]),
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", str(AUDIO_SAMPLE_RATE),
            "-ac", str(AUDIO_CHANNELS),
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(output_path),
        )
        logger.info("Created image clip: %s (%.1fs)", output_path.name, duration)
        return output_path


# ---------------------------------------------------------------------------
# Module-level utilities
# ---------------------------------------------------------------------------


def get_media_duration(file_path: str | Path) -> Optional[float]:
    """
    Get the duration of a media file in seconds via ffprobe.

    Parameters
    ----------
    file_path : str | Path
        Path to the media file.

    Returns
    -------
    float or None
        Duration in seconds, or None if unavailable.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(file_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        info = json.loads(result.stdout)
        duration = info.get("format", {}).get("duration")
        if duration is not None:
            return float(duration)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, FileNotFoundError):
        pass
    return None


def format_duration(seconds: float) -> str:
    """Format seconds as a human-readable ``Xm XXs`` string."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"
