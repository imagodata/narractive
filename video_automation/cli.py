#!/usr/bin/env python3
"""
Video Automation — Main Orchestrator
=====================================
Controls the full video production pipeline: diagrams, narration,
UI automation via PyAutoGUI, recording (OBS or headless frame capture),
and FFmpeg assembly.

Usage (Desktop/OBS mode):
    python -m video_automation --all                    # Run complete pipeline
    python -m video_automation --all --from 5           # Resume from sequence 5
    python -m video_automation --sequence 4             # Run only sequence 4
    python -m video_automation --setup-obs              # Auto-configure OBS

Usage (Docker/headless frame capture):
    python -m video_automation --capture --all          # Frame capture mode
    python -m video_automation --capture --all --capture-fps 15

Common:
    python -m video_automation --diagrams               # Generate diagrams only
    python -m video_automation --narration              # Generate narration audio
    python -m video_automation --calibrate              # Interactive UI calibration
    python -m video_automation --assemble               # Assemble final video
    python -m video_automation --dry-run                # Preview without executing
    python -m video_automation --list                   # List all sequences
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Windows: reconfigure stdout/stderr to UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

import click
import yaml

# ── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("video_automation")


# ── Config loader ──────────────────────────────────────────────────────────

def load_config(config_path: Path) -> dict:
    """Load and return config.yaml as a dict."""
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    logger.debug("Config loaded from %s", config_path)
    try:
        from video_automation.config_schema import validate_config_and_warn

        validate_config_and_warn(cfg)
    except ImportError:
        pass
    return cfg


# ── Sequence loader ───────────────────────────────────────────────────────

def load_sequences_from_package(package_path: str) -> list:
    """
    Dynamically load VideoSequence subclasses from a Python package path.

    Parameters
    ----------
    package_path : str
        Dotted package path, e.g. 'examples.filtermate.sequences'
        or 'my_plugin.sequences.v01'.
    """
    import importlib
    import pkgutil

    from video_automation.sequences.base import VideoSequence

    # Import the package
    pkg = importlib.import_module(package_path)

    # Auto-discover modules in the package
    if hasattr(pkg, "__path__"):
        for info in pkgutil.iter_modules(pkg.__path__):
            if info.ispkg:
                continue
            importlib.import_module(f"{package_path}.{info.name}")

    # If the package exports a SEQUENCES list, use it
    if hasattr(pkg, "SEQUENCES"):
        return pkg.SEQUENCES
    if hasattr(pkg, "V01_SEQUENCES"):
        return pkg.V01_SEQUENCES

    # Otherwise collect all subclasses from this package
    def _collect(base):
        result = []
        for cls in base.__subclasses__():
            if cls.__module__.startswith(package_path):
                result.append(cls)
            result.extend(_collect(cls))
        return result

    classes = _collect(VideoSequence)
    return sorted(classes, key=lambda cls: cls.sequence_id)


# ── CLI entry point ────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--config", type=click.Path(exists=True, dir_okay=False), default=None,
              help="Path to config.yaml")
@click.option("--all", "run_all", is_flag=True, help="Run complete video production pipeline")
@click.option("--sequences-package", "seq_pkg", type=str, default=None, metavar="PKG",
              help="Python package path for sequences (e.g. 'examples.filtermate.sequences')")
@click.option("--sequence", "-s", type=int, default=None, metavar="N",
              help="Run only sequence N")
@click.option("--from", "start_from", type=int, default=None, metavar="N",
              help="Resume pipeline from sequence N")
@click.option("--resume", "resume", is_flag=True,
              help="Automatically resume from the last failed/interrupted sequence (uses pipeline state)")
@click.option("--reset", "reset_state", is_flag=True,
              help="Delete pipeline state file and start fresh")
@click.option("--status", "show_status", is_flag=True,
              help="Show current pipeline state (completed/failed/pending sequences)")
@click.option("--diagrams", is_flag=True, help="Generate Mermaid diagram HTML/PNG files")
@click.option("--diagrams-module", type=str, default=None, metavar="MOD",
              help="Python module path for diagram definitions (e.g. 'examples.filtermate.diagrams.mermaid_definitions')")
@click.option("--narration", is_flag=True, help="Generate TTS narration audio files")
@click.option("--force-narration", "force_narration", is_flag=True,
              help="Regenerate narration audio even when cache is valid (bypass cache)")
@click.option("--narrations-file", type=click.Path(exists=True), default=None,
              help="Path to narrations.yaml file")
@click.option("--video", type=str, default=None, metavar="VXX",
              help="Video script key in narrations.yaml (e.g. 'v01')")
@click.option("--calibrate", is_flag=True, help="Run interactive UI calibration")
@click.option("--setup-obs", "setup_obs", is_flag=True, help="Auto-configure OBS scenes/sources")
@click.option("--subtitles", is_flag=True, help="Generate SRT subtitle files from narrations")
@click.option("--lang", type=str, default=None, metavar="LANG",
              help="Language code (e.g. 'fr', 'en', 'pt') for multilingual operations")
@click.option("--narrations-dir", type=click.Path(exists=True), default=None,
              help="Directory with per-language narration YAML files (fr.yaml, en.yaml, ...)")
@click.option("--quality", type=click.Choice(["draft", "final"]), default="draft",
              help="Encoding quality preset (default: draft)")
@click.option("--assemble", is_flag=True, help="Assemble final video from recorded clips")
@click.option("--capture", is_flag=True, help="Use headless frame capture instead of OBS")
@click.option("--capture-fps", "capture_fps", type=int, default=None, metavar="N",
              help="Override capture FPS")
@click.option("--dry-run", "dry_run", is_flag=True, help="Preview without executing")
@click.option("--list", "list_seqs", is_flag=True, help="List all sequences")
@click.option("--project-name", type=str, default="Video", help="Project name for output labeling")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose (DEBUG) logging")
@click.pass_context
def cli(ctx, config, seq_pkg, run_all, sequence, start_from, resume, reset_state, show_status,
        diagrams, diagrams_module,
        narration, force_narration, narrations_file, video, calibrate, setup_obs, subtitles, lang,
        narrations_dir, quality, assemble, capture, capture_fps, dry_run, list_seqs,
        project_name, verbose):
    """Narractive — orchestrates App + OBS/FrameCapture + TTS + FFmpeg."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Subcommands that manage their own config loading
    if ctx.invoked_subcommand in ("init", "validate-config", "preview", "report"):
        return

    # Find config
    if config is None:
        config = "config.yaml"
        if not Path(config).exists():
            logger.error("No config.yaml found. Specify with --config or create one.")
            sys.exit(1)

    cfg = load_config(Path(config))

    if capture_fps is not None:
        cfg.setdefault("capture", {})["fps"] = capture_fps

    ctx.ensure_object(dict)
    ctx.obj["config"] = cfg
    ctx.obj["dry_run"] = dry_run
    ctx.obj["video"] = video
    ctx.obj["capture"] = capture
    ctx.obj["seq_pkg"] = seq_pkg
    ctx.obj["project_name"] = project_name
    ctx.obj["narrations_file"] = narrations_file
    ctx.obj["diagrams_module"] = diagrams_module
    ctx.obj["config_path"] = Path(config)
    ctx.obj["lang"] = lang
    ctx.obj["narrations_dir"] = narrations_dir
    ctx.obj["quality"] = quality

    # Dispatch
    if reset_state:
        from video_automation.core.pipeline_state import PipelineState
        state = PipelineState.from_config(cfg)
        state.delete()
        click.echo("Pipeline state reset.")
        if not run_all:
            return

    if show_status:
        from video_automation.core.pipeline_state import PipelineState
        state = PipelineState.from_config(cfg)
        click.echo(state.status_table())
        return

    if list_seqs:
        cmd_list(cfg, seq_pkg=seq_pkg, project_name=project_name)
        return

    if calibrate:
        cmd_calibrate(cfg, dry_run, ctx.obj["config_path"])
        return

    if setup_obs:
        cmd_setup_obs(cfg, dry_run)
        return

    if diagrams:
        cmd_diagrams(cfg, dry_run, diagrams_module=diagrams_module)
        return

    if narration:
        cmd_narration(cfg, dry_run, video=video, narrations_file=narrations_file,
                      force=force_narration)
        return

    if subtitles:
        cmd_subtitles(cfg, dry_run, lang=lang, narrations_dir=narrations_dir)
        return

    if assemble:
        cmd_assemble(cfg, dry_run, video=video, project_name=project_name)
        return

    if sequence is not None:
        cmd_run_sequence(cfg, sequence, dry_run, seq_pkg=seq_pkg, use_capture=capture)
        return

    if run_all:
        cmd_run_all(cfg, dry_run, seq_pkg=seq_pkg, use_capture=capture,
                    start_from=start_from, project_name=project_name, video=video,
                    resume=resume)
        return

    click.echo(ctx.get_help())


# ── Sub-command implementations ────────────────────────────────────────────

def _load_sequences(seq_pkg: str | None = None) -> list:
    """Load the right sequence list."""
    if seq_pkg:
        return load_sequences_from_package(seq_pkg)
    logger.error("No --sequences-package specified. Use e.g. --sequences-package examples.filtermate.sequences")
    sys.exit(1)


def cmd_list(config: dict, seq_pkg: str | None = None, project_name: str = "Video") -> None:
    """Print a table of all sequences."""
    seqs = _load_sequences(seq_pkg)
    click.echo(f"\n  {project_name} Sequences\n  " + "-" * 55)
    click.echo(f"  {'#':<4} {'Name':<40} {'Duration':>8}s")
    click.echo("  " + "-" * 55)
    total = 0.0
    for i, SeqClass in enumerate(seqs):
        seq = SeqClass()
        click.echo(f"  {i:<4} {seq.name:<40} {seq.duration_estimate:>8.0f}")
        total += seq.duration_estimate
    click.echo("  " + "-" * 55)
    mins, secs = divmod(int(total), 60)
    click.echo(f"  {'TOTAL':<44} {mins}m {secs:02d}s\n")


def cmd_calibrate(config: dict, dry_run: bool, config_path: Path) -> None:
    """Run interactive calibration."""
    if dry_run:
        click.echo("[DRY-RUN] Would launch calibrate.py")
        return
    import subprocess as sp
    calibrate_script = Path(__file__).parent / "scripts" / "calibrate.py"
    result = sp.run([sys.executable, str(calibrate_script), "--config", str(config_path)])
    if result.returncode != 0:
        sys.exit(result.returncode)


def cmd_setup_obs(config: dict, dry_run: bool) -> None:
    """Configure OBS scenes and sources."""
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from setup_obs import setup_obs  # type: ignore
    setup_obs(config, dry_run=dry_run)


def cmd_diagrams(config: dict, dry_run: bool, diagrams_module: str | None = None) -> None:
    """Generate all Mermaid diagram HTML files."""
    if not diagrams_module:
        logger.error("No --diagrams-module specified.")
        sys.exit(1)

    import importlib
    mod = importlib.import_module(diagrams_module)
    DIAGRAMS = mod.DIAGRAMS

    from video_automation.core.diagram_generator import DiagramGenerator
    gen = DiagramGenerator(config.get("diagrams", {}))
    out_dir = Path(config.get("diagrams", {}).get("output_dir", "output/diagrams"))

    if dry_run:
        click.echo(f"[DRY-RUN] Would generate {len(DIAGRAMS)} diagrams in {out_dir}")
        return

    click.echo(f"\nGenerating {len(DIAGRAMS)} diagrams...")
    html_paths = gen.generate_all_diagrams(DIAGRAMS, out_dir)
    click.echo(f"  ok HTML files in {out_dir}")

    click.echo("Rendering to PNG (requires Playwright)...")
    png_paths = gen.render_all_to_png(html_paths, out_dir)
    if png_paths:
        click.echo(f"  ok PNG files in {out_dir}")
    else:
        click.echo("  !! No PNG files (install Playwright)")

    click.echo(f"\nDone! {len(html_paths)} HTML, {len(png_paths)} PNG diagrams.\n")


def cmd_subtitles(
    config: dict, dry_run: bool,
    lang: str | None = None, narrations_dir: str | None = None,
) -> None:
    """Generate SRT subtitle files from narration texts."""
    from video_automation.core.narrator import load_narrations_multilingual
    from video_automation.core.subtitles import SubtitleGenerator

    sub_cfg = config.get("subtitles", {})
    if not sub_cfg.get("enabled", True):
        click.echo("Subtitles disabled in config.yaml (subtitles.enabled: false)")
        return

    gen = SubtitleGenerator(sub_cfg)
    languages_cfg = config.get("languages", {})

    # Determine narrations directory
    narr_dir = Path(narrations_dir) if narrations_dir else Path("narrations")
    if not narr_dir.exists():
        click.echo(f"Narrations directory not found: {narr_dir}")
        return

    # Determine languages
    if lang:
        langs = [lang]
    elif languages_cfg:
        langs = list(languages_cfg.keys())
    else:
        # Auto-detect from YAML files in narrations dir
        langs = [f.stem for f in sorted(narr_dir.glob("*.yaml"))]

    if not langs:
        click.echo("No languages found. Use --lang or configure languages in config.yaml.")
        return

    total = 0
    for l_code in langs:
        narrations = load_narrations_multilingual(narr_dir, l_code)
        if not narrations:
            click.echo(f"  [{l_code.upper()}] No narrations found, skipping.")
            continue

        out_template = sub_cfg.get("output_dir", "output/{lang}/subtitles")
        out_dir = Path(out_template.replace("{lang}", l_code))

        if dry_run:
            click.echo(f"  [{l_code.upper()}] Would generate {len(narrations)} SRT files in {out_dir}")
            continue

        click.echo(f"\n  [{l_code.upper()}] Generating {len(narrations)} SRT files…")
        results = gen.generate_for_language(narrations, out_dir, lang=l_code)
        total += len(results)
        for seq_id, path in results.items():
            click.echo(f"    {seq_id}.srt")

    click.echo(f"\nDone! {total} SRT files generated.\n")


def cmd_narration(config: dict, dry_run: bool, video: str | None = None,
                  narrations_file: str | None = None, force: bool = False) -> None:
    """Generate TTS narration audio for all sequences."""
    from video_automation.core.narrator import Narrator, get_narration_texts

    if not narrations_file:
        narrations_file = "narrations.yaml"

    narrator = Narrator(config.get("narration", {}))
    narration_texts = get_narration_texts(narrations_file, video)
    label = video.upper() if video else "original"
    out_dir = Path(config.get("narration", {}).get("output_dir", "output/narration"))
    if video:
        out_dir = out_dir / video

    if dry_run:
        click.echo(f"[DRY-RUN] Would generate {len(narration_texts)} narration files ({label})")
        if force:
            click.echo("  (cache bypass: --force-narration)")
        return

    if force:
        click.echo("  Cache bypassed via --force-narration")
    click.echo(f"\nGenerating narration for {len(narration_texts)} sequences ({label})...")
    results = narrator.generate_all_narrations(narration_texts, out_dir, force=force)
    click.echo(f"\nDone! {len(results)} audio files in {out_dir}\n")

    total = 0.0
    for seq_id, path in results.items():
        dur = narrator.get_narration_duration(path)
        total += dur
        click.echo(f"  {seq_id:20s} {dur:5.1f}s  -> {path.name}")
    mins, secs = divmod(int(total), 60)
    click.echo(f"\n  Total narration: {mins}m {secs:02d}s\n")


def cmd_run_sequence(
    config: dict, seq_num: int, dry_run: bool,
    seq_pkg: str | None = None, use_capture: bool = False,
) -> None:
    """Run a single sequence."""
    seqs = _load_sequences(seq_pkg)
    if seq_num < 0 or seq_num >= len(seqs):
        click.echo(f"Error: sequence {seq_num} out of range (0-{len(seqs) - 1})")
        sys.exit(1)

    SeqClass = seqs[seq_num]
    seq = SeqClass()

    if dry_run:
        backend = "FrameCapture" if use_capture else "OBS"
        click.echo(f"[DRY-RUN] Would run: {seq.name} (backend: {backend})")
        return

    click.echo(f"\nRunning sequence {seq_num}: {seq.name}\n")
    recorder, app = _init_controllers(config, use_capture=use_capture)
    with recorder:
        recorder.start_recording()
        recorder.wait_for_recording_start()
        try:
            seq.run(recorder, app, config)
        finally:
            output_path = recorder.stop_recording()
            click.echo(f"\n  Recording saved: {output_path}")


def cmd_run_all(
    config: dict, dry_run: bool,
    seq_pkg: str | None = None, use_capture: bool = False,
    start_from: int | None = None, project_name: str = "Video",
    video: str | None = None,
    resume: bool = False,
) -> None:
    """Run the complete video production pipeline."""
    from video_automation.core.pipeline_state import PipelineState

    SEQUENCES = _load_sequences(seq_pkg)
    backend = "FrameCapture" if use_capture else "OBS"

    click.echo("\n" + "=" * 65)
    click.echo(f"  {project_name} — Complete Video Production ({backend})")
    click.echo("=" * 65)

    # Build ordered list of sequence IDs for state tracking
    seq_instances = [SeqClass() for SeqClass in SEQUENCES]
    all_seq_ids = [
        getattr(seq, "sequence_id", f"seq{i:02d}")
        for i, seq in enumerate(seq_instances)
    ]

    # Load / initialise pipeline state
    state = PipelineState.from_config(config)

    # Determine effective start index
    if resume:
        effective_start = state.resume_from_index(all_seq_ids)
        if effective_start > 0:
            click.echo(
                f"\n  Resuming from sequence {effective_start} "
                f"({all_seq_ids[effective_start] if effective_start < len(all_seq_ids) else 'end'})"
                f" — {len(state.completed_ids())} already completed."
            )
    elif start_from is not None:
        if start_from < 0 or start_from >= len(SEQUENCES):
            click.echo(f"Error: --from {start_from} out of range (0-{len(SEQUENCES) - 1})")
            sys.exit(1)
        effective_start = start_from
    else:
        effective_start = 0

    if not resume:
        # Fresh run: reinitialise state (keeps existing entries on partial --from)
        state.start_run(sequences_package=seq_pkg or "", total=len(SEQUENCES))
        state.save()

    if dry_run:
        click.echo(f"\n[DRY-RUN] Would run these sequences (backend: {backend}):\n")
        for i, seq in enumerate(seq_instances):
            skipped = i < effective_start
            marker = "SKIP" if skipped else " RUN"
            click.echo(f"  [{marker}] [{i}] {seq.name:<40} {seq.duration_estimate:.0f}s")
        return

    _check_prerequisites(config, use_capture=use_capture)

    recorder, app = _init_controllers(config, use_capture=use_capture)

    recording_files: list[str] = []
    all_timeline_results: list[tuple[str, object]] = []

    with recorder:
        for i, SeqClass in enumerate(SEQUENCES):
            if i < effective_start:
                continue

            seq = seq_instances[i]
            seq_id = all_seq_ids[i]

            # Skip already-completed sequences when resuming
            if resume and state.is_completed(seq_id):
                click.echo(f"\n  [SKIP] [{i}/{len(SEQUENCES)-1}] {seq.name} (already completed)")
                recorded = state.get_recordings().get(seq_id)
                if recorded:
                    recording_files.append(recorded)
                continue

            click.echo(f"\n[{i}/{len(SEQUENCES)-1}] {seq.name}")
            state.mark_running(seq_id)
            state.save()

            recorder.start_recording()
            recorder.wait_for_recording_start()
            output_path = None
            try:
                seq.run(recorder, app, config)
            except KeyboardInterrupt:
                click.echo("\n  Interrupted by user.")
                output_path = recorder.stop_recording()
                if output_path:
                    recording_files.append(output_path)
                    all_timeline_results.append((output_path, seq.timeline_result))
                    state.mark_completed(seq_id, recording_path=output_path)
                    state.save()
                break
            except Exception as exc:
                logger.error("Sequence %d failed: %s", i, exc)
                click.echo(f"  x Sequence {i} failed: {exc}")
                output_path = recorder.stop_recording()
                state.mark_failed(seq_id, error=str(exc))
                state.save()
                if output_path:
                    recording_files.append(output_path)
                    all_timeline_results.append((output_path, seq.timeline_result))
                time.sleep(3)
                continue
            finally:
                if output_path is None:
                    output_path = recorder.stop_recording()
                if output_path and output_path not in recording_files:
                    recording_files.append(output_path)
                    click.echo(f"  ok Saved: {output_path}")
                    all_timeline_results.append((output_path, seq.timeline_result))
                    if seq.timeline_result:
                        click.echo(
                            f"       Timeline: "
                            f"{len(seq.timeline_result.narration_timecodes)} narration segments"
                        )
                    if not state.is_completed(seq_id):
                        state.mark_completed(seq_id, recording_path=output_path)
                        state.save()
                time.sleep(3)

    click.echo(f"\nRecorded {len(recording_files)} clips.")

    if recording_files:
        click.echo("\nProceeding to assembly...")
        cmd_assemble(
            config, dry_run=False, clips=recording_files, video=video,
            project_name=project_name, timeline_results=all_timeline_results,
        )


def cmd_assemble(
    config: dict, dry_run: bool,
    clips: list[str] | None = None, video: str | None = None,
    project_name: str = "Video",
    timeline_results: list[tuple[str, object]] | None = None,
) -> None:
    """Assemble final video from recorded clips + narration."""
    from video_automation.core.video_assembler import VideoAssembler

    out_cfg = config.get("output", {})
    assembler = VideoAssembler(out_cfg)
    final_dir = Path(out_cfg.get("final_dir", "output/final"))
    narr_dir = Path(config.get("narration", {}).get("output_dir", "output/narration"))
    if video:
        narr_dir = narr_dir / video

    if clips is None:
        default_obs_dir = Path.home() / "Videos" / project_name
        obs_output = Path(config.get("obs", {}).get("output_dir", str(default_obs_dir)))
        clips = sorted(str(p) for p in obs_output.glob("*.mkv"))
        if not clips:
            click.echo(f"No MKV clips found in {obs_output}.")
            return

    safe_name = project_name.lower().replace(" ", "_")
    output_name = f"{safe_name}_{video}_final.mp4" if video else f"{safe_name}_final.mp4"

    has_timecodes = (
        timeline_results
        and any(tr is not None for _, tr in timeline_results)
    )

    if dry_run:
        mode = "timecode-based" if has_timecodes else "legacy concat"
        click.echo(f"[DRY-RUN] Would assemble {len(clips)} clips ({mode})")
        return

    if has_timecodes:
        click.echo(f"\nAssembling {len(clips)} clips with timecode-based narration...")
        final_path = assembler.create_final_video_with_timecodes(
            clips=clips,
            timeline_results=[tr for _, tr in timeline_results],
            output_path=final_dir / output_name,
        )
    else:
        narration_files = sorted(narr_dir.glob("*_narration.mp3"))
        click.echo(f"\nAssembling {len(clips)} clips + {len(narration_files)} narrations (legacy)...")
        final_path = assembler.create_final_video(
            clips=clips,
            narrations=list(narration_files),
            output_path=final_dir / output_name,
        )

    click.echo(f"\n  ok Final video: {final_path}\n")


# ── Helpers ────────────────────────────────────────────────────────────────

def _init_controllers(config: dict, use_capture: bool = False):
    from video_automation.core.app_automator import AppAutomator

    if use_capture:
        from video_automation.core.frame_capturer import FrameCapturer
        recorder = FrameCapturer(config.get("capture", {}))
    else:
        from video_automation.core.obs_controller import OBSController
        recorder = OBSController(config.get("obs", {}))

    app = AppAutomator(config)
    return recorder, app


def _check_prerequisites(config: dict, use_capture: bool = False) -> None:
    import shutil

    backend = "FrameCapture" if use_capture else "OBS"
    click.echo(f"\nChecking prerequisites (backend: {backend})...")

    checks = [
        ("ffmpeg", "FFmpeg"),
    ]
    for cmd, label in checks:
        if shutil.which(cmd):
            click.echo(f"  ok {label}")
        else:
            click.echo(f"  !! {label} not found on PATH")

    try:
        import pyautogui  # type: ignore
        click.echo("  ok pyautogui")
    except ImportError:
        click.echo("  xx pyautogui not installed")

    if use_capture:
        for tool in ["xdotool", "scrot", "import"]:
            if shutil.which(tool):
                click.echo(f"  ok {tool}")
            else:
                click.echo(f"  !! {tool} not found (optional)")
    else:
        try:
            import obsws_python  # type: ignore
            click.echo("  ok obsws-python")
        except ImportError:
            click.echo("  xx obsws-python not installed")

    click.echo()


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    try:
        cli(standalone_mode=False)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()



# ── `narractive init` ──────────────────────────────────────────────────────


@cli.command("init")
@click.argument("project_dir", default=".", type=click.Path())
@click.option(
    "--no-interactive", "no_interactive", is_flag=True, help="Skip all prompts and use defaults."
)
def cmd_init(project_dir: str, no_interactive: bool) -> None:
    """Scaffold a new Narractive project directory."""
    from video_automation.scripts.init_project import scaffold_project

    project_path = Path(project_dir).resolve()
    dir_name = project_path.name or "my_project"

    if no_interactive:
        display_name = dir_name
        app_window = dir_name
        tts_engine = "edge-tts"
        languages = ["fr"]
        recording_backend = "obs"
    else:
        display_name = click.prompt("Project display name", default=dir_name)
        app_window = click.prompt("App window title (substring to match)", default=display_name)
        tts_engine = click.prompt(
            "TTS engine",
            type=click.Choice(["edge-tts", "elevenlabs", "kokoro", "f5-tts"]),
            default="edge-tts",
        )
        lang_input = click.prompt("Languages (comma-separated, e.g. fr,en)", default="fr")
        languages = [lang_code.strip() for lang_code in lang_input.split(",") if lang_code.strip()]
        recording_backend = click.prompt(
            "Recording backend",
            type=click.Choice(["obs", "headless"]),
            default="obs",
        )

    click.echo(f"\nScaffolding project in {project_path}...")
    next_steps = scaffold_project(
        project_dir=project_path,
        project_name=dir_name,
        app_window=app_window,
        tts_engine=tts_engine,
        languages=languages,
        recording_backend=recording_backend,
        display_name=display_name,
    )
    click.echo(next_steps)


# ── `narractive validate-config` ──────────────────────────────────────────


@cli.command("validate-config")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False),
    default="config.yaml",
    show_default=True,
    help="Path to config.yaml to validate.",
)
def cmd_validate_config(config_path: str) -> None:
    """Validate config.yaml against the Narractive schema."""
    from video_automation.config_schema import is_pydantic_available, validate_config

    if not is_pydantic_available():
        click.echo("pydantic is not installed. Install with:\n  pip install 'narractive[config]'")
        return

    raw = load_config(Path(config_path))
    cfg = validate_config(raw)
    click.echo(f"  ok Config is valid: {config_path}")
    click.echo(f"     narration engine : {cfg.narration.engine}")
    langs = list(cfg.languages.keys()) if cfg.languages else []
    click.echo(f"     languages        : {langs or '(none)'}")


# ── `narractive preview` ──────────────────────────────────────────────────


@cli.command("preview")
@click.option(
    "--sequence",
    "-s",
    "sequence_id",
    type=str,
    default=None,
    metavar="SEQ",
    help="Sequence ID to preview (e.g. seq01).",
)
@click.option("--all", "preview_all", is_flag=True, help="Preview all sequences.")
@click.option("--lang", type=str, default="fr", show_default=True, help="Language code.")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False),
    default="config.yaml",
    show_default=True,
    help="Path to config.yaml.",
)
@click.option("--no-play", "no_play", is_flag=True, help="Print audio path without playing.")
def cmd_preview(
    sequence_id: str | None,
    preview_all: bool,
    lang: str,
    config_path: str,
    no_play: bool,
) -> None:
    """Preview narration audio for one or all sequences."""
    import time as _time

    from video_automation.core.narrator import Narrator, load_narrations_multilingual

    cfg = load_config(Path(config_path))
    narr_cfg = cfg.get("narration", {})
    narrator = Narrator(narr_cfg)

    narr_dir = Path("narrations")
    if not narr_dir.exists():
        click.echo(f"Narrations directory not found: {narr_dir}")
        sys.exit(1)

    narrations = load_narrations_multilingual(narr_dir, lang)
    if not narrations:
        click.echo(f"No narrations found for lang={lang} in {narr_dir}")
        sys.exit(1)

    out_dir = Path(narr_cfg.get("output_dir", "output/narration")) / lang

    if sequence_id and not preview_all:
        items = [(sequence_id, narrations.get(sequence_id, ""))]
        if not narrations.get(sequence_id):
            click.echo(f"Sequence '{sequence_id}' not found in {narr_dir}/{lang}.yaml")
            sys.exit(1)
    else:
        items = list(narrations.items())

    for seq_id, text in items:
        if not text:
            continue

        audio_path = out_dir / f"{seq_id}_narration.mp3"

        # Generate if not cached
        if not audio_path.exists():
            click.echo(f"  Generating {seq_id}...")
            out_dir.mkdir(parents=True, exist_ok=True)
            try:
                audio_path = narrator.generate_narration(text, audio_path)
            except Exception as exc:
                click.echo(f"  !! TTS failed for {seq_id}: {exc}")
                continue

        # Estimate duration
        try:
            duration = narrator.get_narration_duration(audio_path)
        except Exception:
            duration = 0.0

        preview_text = text[:80].replace("\n", " ")
        click.echo(f"\n  [{seq_id}] ~{duration:.1f}s\n  {preview_text!r}\n  {audio_path}")

        if no_play:
            continue

        # Playback: try ffplay first, fall back to playsound
        _play_audio(audio_path)

        if preview_all and len(items) > 1:
            _time.sleep(0.5)


def _play_audio(audio_path: Path) -> None:
    """Play an audio file using ffplay or playsound."""
    import subprocess as sp

    try:
        sp.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_path)],
            timeout=120,
            check=False,
        )
    except FileNotFoundError:
        # ffplay not available, try playsound
        try:
            import playsound  # type: ignore

            playsound.playsound(str(audio_path))
        except ImportError:
            click.echo("  (install ffplay or playsound to play audio)")
    except Exception as exc:
        click.echo(f"  !! Playback error: {exc}")


# ── `narractive report` ───────────────────────────────────────────────────


@cli.command("report")
@click.argument("build_dir", default="output", type=click.Path())
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False),
    default="config.yaml",
    show_default=True,
    help="Path to config.yaml.",
)
@click.option(
    "--project-name",
    "project_name",
    type=str,
    default=None,
    help="Project display name (defaults to build_dir name).",
)
@click.option(
    "--video",
    "video",
    type=str,
    default=None,
    metavar="VXX",
    help="Video script key (e.g. 'v01') for locating narration sub-directories.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False),
    default=None,
    metavar="FILE",
    help="Write machine-readable JSON report to FILE (e.g. report.json).",
)
@click.option("--json", "as_json", is_flag=True, help="Print JSON report to stdout.")
def cmd_report(
    build_dir: str,
    config_path: str,
    project_name: str | None,
    video: str | None,
    output_path: str | None,
    as_json: bool,
) -> None:
    """Show a production summary for BUILD_DIR (default: output/).

    Scans clips, narration audio, subtitle files, and the final assembled
    video to report durations, sizes, and per-language subtitle coverage.

    Examples::

        narractive report
        narractive report output/ --project-name "My Demo" --video v01
        narractive report --json
        narractive report --output report.json
    """
    import json as _json

    from video_automation.core.report import ProductionReport

    cfg = load_config(Path(config_path))
    build_path = Path(build_dir).resolve()
    pname = project_name or build_path.name or "Production"

    rpt = ProductionReport(cfg, build_dir=build_path)
    rpt.collect(project_name=pname, video=video)

    if as_json:
        click.echo(_json.dumps(rpt.to_dict(), indent=2, ensure_ascii=False))
        return

    rpt.print_table()

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            _json.dump(rpt.to_dict(), f, indent=2, ensure_ascii=False)
        click.echo(f"  JSON report written to {out}")
