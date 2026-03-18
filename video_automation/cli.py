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
@click.option("--diagrams", is_flag=True, help="Generate Mermaid diagram HTML/PNG files")
@click.option("--diagrams-module", type=str, default=None, metavar="MOD",
              help="Python module path for diagram definitions (e.g. 'examples.filtermate.diagrams.mermaid_definitions')")
@click.option("--narration", is_flag=True, help="Generate TTS narration audio files")
@click.option("--narrations-file", type=click.Path(exists=True), default=None,
              help="Path to narrations.yaml file")
@click.option("--video", type=str, default=None, metavar="VXX",
              help="Video script key in narrations.yaml (e.g. 'v01')")
@click.option("--calibrate", is_flag=True, help="Run interactive UI calibration")
@click.option("--setup-obs", "setup_obs", is_flag=True, help="Auto-configure OBS scenes/sources")
@click.option("--assemble", is_flag=True, help="Assemble final video from recorded clips")
@click.option("--capture", is_flag=True, help="Use headless frame capture instead of OBS")
@click.option("--capture-fps", "capture_fps", type=int, default=None, metavar="N",
              help="Override capture FPS")
@click.option("--dry-run", "dry_run", is_flag=True, help="Preview without executing")
@click.option("--list", "list_seqs", is_flag=True, help="List all sequences")
@click.option("--project-name", type=str, default="Video", help="Project name for output labeling")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose (DEBUG) logging")
@click.pass_context
def cli(ctx, config, seq_pkg, run_all, sequence, start_from, diagrams, diagrams_module,
        narration, narrations_file, video, calibrate, setup_obs, assemble,
        capture, capture_fps, dry_run, list_seqs, project_name, verbose):
    """Video Automation — orchestrates App + OBS/FrameCapture + FFmpeg."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

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

    # Dispatch
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
        cmd_narration(cfg, dry_run, video=video, narrations_file=narrations_file)
        return

    if assemble:
        cmd_assemble(cfg, dry_run, video=video, project_name=project_name)
        return

    if sequence is not None:
        cmd_run_sequence(cfg, sequence, dry_run, seq_pkg=seq_pkg, use_capture=capture)
        return

    if run_all:
        cmd_run_all(cfg, dry_run, seq_pkg=seq_pkg, use_capture=capture,
                    start_from=start_from, project_name=project_name, video=video)
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


def cmd_narration(config: dict, dry_run: bool, video: str | None = None,
                  narrations_file: str | None = None) -> None:
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
        return

    click.echo(f"\nGenerating narration for {len(narration_texts)} sequences ({label})...")
    results = narrator.generate_all_narrations(narration_texts, out_dir)
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
) -> None:
    """Run the complete video production pipeline."""
    SEQUENCES = _load_sequences(seq_pkg)
    backend = "FrameCapture" if use_capture else "OBS"

    click.echo("\n" + "=" * 65)
    click.echo(f"  {project_name} — Complete Video Production ({backend})")
    click.echo("=" * 65)

    if start_from is not None:
        if start_from < 0 or start_from >= len(SEQUENCES):
            click.echo(f"Error: --from {start_from} out of range (0-{len(SEQUENCES) - 1})")
            sys.exit(1)

    if dry_run:
        click.echo(f"\n[DRY-RUN] Would run these sequences (backend: {backend}):\n")
        for i, SeqClass in enumerate(SEQUENCES):
            seq = SeqClass()
            skipped = start_from is not None and i < start_from
            marker = "SKIP" if skipped else " RUN"
            click.echo(f"  [{marker}] [{i}] {seq.name:<40} {seq.duration_estimate:.0f}s")
        return

    _check_prerequisites(config, use_capture=use_capture)

    recorder, app = _init_controllers(config, use_capture=use_capture)

    recording_files: list[str] = []
    all_timeline_results: list[tuple[str, object]] = []

    with recorder:
        for i, SeqClass in enumerate(SEQUENCES):
            if start_from is not None and i < start_from:
                continue

            seq = SeqClass()
            click.echo(f"\n[{i}/{len(SEQUENCES)-1}] {seq.name}")

            recorder.start_recording()
            recorder.wait_for_recording_start()
            try:
                seq.run(recorder, app, config)
            except KeyboardInterrupt:
                click.echo("\n  Interrupted by user.")
                output_path = recorder.stop_recording()
                if output_path:
                    recording_files.append(output_path)
                    all_timeline_results.append((output_path, seq.timeline_result))
                break
            except Exception as exc:
                logger.error("Sequence %d failed: %s", i, exc)
                click.echo(f"  x Sequence {i} failed: {exc}")
            finally:
                output_path = recorder.stop_recording()
                if output_path:
                    recording_files.append(output_path)
                    click.echo(f"  ok Saved: {output_path}")
                    all_timeline_results.append((output_path, seq.timeline_result))
                    if seq.timeline_result:
                        click.echo(f"       Timeline: {len(seq.timeline_result.narration_timecodes)} narration segments")
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
