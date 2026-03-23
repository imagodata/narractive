# Narractive

[![CI](https://github.com/imagodata/narractive/actions/workflows/ci.yml/badge.svg)](https://github.com/imagodata/narractive/actions/workflows/ci.yml)

A modular Python framework for automated video production — from narration to final cut.

Narractive orchestrates the full pipeline: UI interaction (PyAutoGUI), screen recording (OBS or headless), text-to-speech narration, Mermaid diagram generation, subtitle generation, and FFmpeg assembly. Script your sequences, define narration cues, and let the framework produce polished demo videos hands-free.

## Features

- **Dual recording backends**: OBS WebSocket (desktop) or headless frame capture (Docker/Xvfb)
- **Multi-engine TTS narration**: edge-tts (free), ElevenLabs (premium), F5-TTS (voice cloning), XTTS v2 (multilingual cloning)
- **Timeline-synchronized sequences**: Narration cues paired with UI actions
- **Mermaid diagram slides**: HTML + PNG via Playwright, mmdc, or mermaid.ink API (zero-dep)
- **SRT subtitle generation**: WPM-based timing from narration text, multilingual defaults
- **Multilingual diagram labels**: i18n base class with automatic language fallback
- **FFmpeg post-production**: Quality presets (draft/final), subtitle burn, intro/outro from images, duration matching
- **Interactive calibration**: Record UI element positions for pixel-perfect automation
- **Docker support**: Reproducible headless production in CI/CD

## Quick Start

```bash
# Install from PyPI
pip install narractive

# Or install from source
pip install -e .

# Copy and configure
cp config.template.yaml config.yaml

# Calibrate UI positions (interactive)
narractive --calibrate --config config.yaml

# Generate subtitles from narrations (multilingual)
narractive --subtitles --narrations-dir narrations/ --config config.yaml

# Generate subtitles (single language)
narractive --subtitles --lang fr --narrations-dir narrations/

# Generate diagrams
narractive --diagrams --diagrams-module my_project.diagrams.mermaid_definitions

# Record all sequences
narractive --all --sequences-package my_project.sequences --config config.yaml

# Assemble final video (fast preview)
narractive --assemble --quality draft --project-name "My Project"

# Assemble final video (publication quality)
narractive --assemble --quality final --project-name "My Project"

# Or headless (Docker)
docker compose run --rm video --all --sequences-package my_project.sequences
```

## Architecture

```
narractive/
├── video_automation/              # Framework (pip-installable)
│   ├── core/                      # Generic modules
│   │   ├── app_automator.py      # PyAutoGUI + window control
│   │   ├── obs_controller.py     # OBS WebSocket 5.x
│   │   ├── frame_capturer.py     # Headless Xvfb capture
│   │   ├── narrator.py           # TTS (edge-tts/ElevenLabs/F5-TTS/XTTS v2)
│   │   ├── subtitles.py          # SRT generation from narration text
│   │   ├── timeline.py           # Narration-synchronized cues
│   │   ├── diagram_generator.py  # Mermaid → HTML/PNG (Playwright/mmdc/API)
│   │   └── video_assembler.py    # FFmpeg post-production + quality presets
│   ├── sequences/
│   │   └── base.py               # VideoSequence + TimelineSequence
│   ├── bridges/
│   │   ├── f5_tts_bridge.py      # F5-TTS subprocess bridge
│   │   └── xtts_bridge.py        # XTTS v2 (Coqui TTS) subprocess bridge
│   ├── diagrams/
│   │   ├── i18n.py               # Multilingual diagram labels
│   │   └── template.html         # Mermaid HTML template
│   ├── scripts/
│   │   ├── calibrate.py          # Interactive UI calibration
│   │   └── setup_obs.py          # OBS auto-configuration
│   └── cli.py                    # Click-based CLI
│
├── examples/
│   └── filtermate/               # Example project (QGIS plugin demo)
│
├── config.template.yaml          # Configuration template
├── Dockerfile                    # Headless Docker image
├── docker-compose.yml
└── pyproject.toml
```

## Creating Sequences for Your App

### 1. Simple sequence (manual timing)

```python
from video_automation.sequences.base import VideoSequence

class MyIntro(VideoSequence):
    name = "Introduction"
    sequence_id = "seq00"
    duration_estimate = 30.0
    obs_scene = "Main"

    def execute(self, obs, app, config):
        app.focus_app()
        app.click_at("my_button")
        app.wait(2.0)
        app.scroll_down(3)
```

### 2. Timeline sequence (narration-synchronized)

```python
from video_automation.sequences.base import TimelineSequence
from video_automation.core.timeline import NarrationCue

class MyDemo(TimelineSequence):
    name = "Live Demo"
    sequence_id = "seq01"
    duration_estimate = 60.0

    def build_timeline(self, obs, app, config):
        return [
            NarrationCue(
                text="Welcome to the demo.",
                actions=lambda: app.wait(1.0),
                sync="during",
            ),
            NarrationCue(
                text="Let's open the settings.",
                actions=lambda: app.click_at("settings_button"),
                sync="after",
            ),
        ]
```

### 3. Multilingual diagram labels

```python
from video_automation.diagrams.i18n import DiagramLabels

labels = DiagramLabels(
    labels={
        "server": {"fr": "Serveur", "en": "Server", "pt": "Servidor"},
        "client": {"fr": "Client", "en": "Client", "pt": "Cliente"},
    },
    titles={
        "architecture": {"fr": "Architecture", "en": "Architecture"},
    },
    default_lang="fr",
)

name = labels.l("server", "en")  # "Server"
```

### 4. Register sequences

Create `my_project/sequences/__init__.py`:

```python
from my_project.sequences.seq00_intro import MyIntro
from my_project.sequences.seq01_demo import MyDemo

SEQUENCES = [MyIntro, MyDemo]
```

Then run:
```bash
narractive --list --sequences-package my_project.sequences
narractive --all --sequences-package my_project.sequences
```

## Configuration

See `config.template.yaml` for all available options. Key sections:

| Section | Purpose |
|---------|---------|
| `obs` | OBS WebSocket connection, scenes, output directory |
| `app` | Window title, panel name, calibrated UI positions |
| `timing` | Click/type/scroll delays, transition pauses |
| `diagrams` | Mermaid rendering (resolution, theme, colors) |
| `narration` | TTS engine, voice, speed, F5-TTS/XTTS options |
| `subtitles` | SRT generation (enabled, max chars, max lines) |
| `capture` | Headless frame capture (FPS, resolution, display) |
| `output` | Final video encoding (resolution, fps, codec, quality preset) |

## TTS Engines

| Engine | Cost | Quality | Multilingual | Setup |
|--------|------|---------|-------------|-------|
| edge-tts | Free | Good | Yes | `pip install edge-tts` (included) |
| ElevenLabs | Paid | Excellent | Yes | `pip install elevenlabs` + API key |
| F5-TTS | Free | Excellent | No | Conda env + GPU recommended |
| XTTS v2 | Free | Excellent | Yes | `pip install TTS` + GPU recommended |

## Requirements

- Python 3.10+
- FFmpeg (for video assembly)
- OBS Studio (desktop mode) or Docker (headless mode)
- Your target application installed and running

## License

MIT
