# Video Automation — Project Overview

## Purpose
Modular Python framework for automating QGIS plugin demo video production. 
Pipeline: UI interaction (PyAutoGUI) → recording (OBS / headless Xvfb) → narration (TTS) → Mermaid diagrams → FFmpeg assembly.

## Tech Stack
- Python 3.10+ (pip-installable package)
- PyAutoGUI for UI automation
- OBS WebSocket 5.x (obsws-python) or headless frame capture (Xvfb)
- edge-tts / ElevenLabs / F5-TTS for narration
- Playwright for diagram PNG rendering
- FFmpeg for video assembly
- Click for CLI
- PyYAML for config
- Docker support (QGIS + Xvfb headless)

## Structure
- `video_automation/` — Framework (pip-installable)
  - `core/` — narrator, qgis_automator, obs_controller, frame_capturer, timeline, diagram_generator, video_assembler
  - `sequences/base.py` — VideoSequence (ABC) + TimelineSequence
  - `cli.py` — Click-based CLI entry point
  - `scripts/` — calibrate.py, setup_obs.py
- `examples/filtermate/` — FilterMate plugin example
  - `sequences/` — 11 original (seq00-10) + 7 v01 (timeline-based)
  - `diagrams/mermaid_definitions.py` — 20 Mermaid diagrams
  - `*_standalone.py` — 3 standalone scripts (bypassing framework)
  - `narrations.yaml` — Centralized narration texts

## Commands
- `pip install -e .` — Install in dev mode
- `video-automation --list --sequences-package examples.filtermate.sequences`
- `video-automation --narration --narrations-file narrations.yaml`
- `video-automation --diagrams --diagrams-module examples.filtermate.diagrams.mermaid_definitions`
- `video-automation --all --sequences-package examples.filtermate.sequences`
- `docker compose run --rm video --all`

## Style
- NumPy-style docstrings
- Type hints (mostly, using `Optional`, `Union` from `typing`)
- Logging via `logging.getLogger()`
- No tests yet (tests/ dir is empty)
- No linter/formatter config (no ruff/black/isort in pyproject.toml)
