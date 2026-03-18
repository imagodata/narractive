# Video Automation

A modular Python framework for automating QGIS plugin demo video production.

Automate the entire pipeline: UI interaction (PyAutoGUI), recording (OBS or headless), narration (TTS), Mermaid diagrams, and FFmpeg assembly.

## Features

- **Dual recording backends**: OBS WebSocket (desktop) or headless frame capture (Docker/Xvfb)
- **Multi-engine TTS narration**: edge-tts (free), ElevenLabs (premium), F5-TTS (voice cloning)
- **Timeline-synchronized sequences**: Narration cues paired with UI actions
- **Mermaid diagram slides**: HTML + PNG generation with dark theme
- **FFmpeg post-production**: Clip concatenation, narration mixing, timecode-based assembly
- **Interactive calibration**: Record UI element positions for pixel-perfect automation
- **Docker support**: Reproducible headless production in CI/CD

## Quick Start

```bash
# Install
pip install -e .

# Copy and configure
cp config.template.yaml config.yaml

# Calibrate UI positions (interactive)
video-automation --calibrate --config config.yaml

# Generate narration
video-automation --narration --narrations-file narrations.yaml

# Generate diagrams
video-automation --diagrams --diagrams-module my_project.diagrams.mermaid_definitions

# Record all sequences
video-automation --all --sequences-package my_project.sequences --config config.yaml

# Or headless (Docker)
docker compose run --rm video --all --sequences-package my_project.sequences
```

## Architecture

```
video-automation/
├── video_automation/              # Framework (pip-installable)
│   ├── core/                      # Generic modules
│   │   ├── qgis_automator.py     # PyAutoGUI + QGIS control
│   │   ├── obs_controller.py     # OBS WebSocket 5.x
│   │   ├── frame_capturer.py     # Headless Xvfb capture
│   │   ├── narrator.py           # TTS (edge-tts/ElevenLabs/F5-TTS)
│   │   ├── timeline.py           # Narration-synchronized cues
│   │   ├── diagram_generator.py  # Mermaid → HTML/PNG
│   │   └── video_assembler.py    # FFmpeg post-production
│   ├── sequences/
│   │   └── base.py               # VideoSequence + TimelineSequence
│   ├── scripts/
│   │   ├── calibrate.py          # Interactive UI calibration
│   │   └── setup_obs.py          # OBS auto-configuration
│   └── cli.py                    # Click-based CLI
│
├── examples/
│   └── filtermate/               # FilterMate plugin example
│       ├── sequences/            # 11 original + 7 v01 sequences
│       ├── diagrams/             # 20 Mermaid diagram definitions
│       ├── narrations.yaml       # French narration scripts
│       └── config.yaml           # Calibrated FilterMate positions
│
├── config.template.yaml          # Configuration template
├── Dockerfile                    # Headless Docker image
├── docker-compose.yml
└── pyproject.toml
```

## Creating Sequences for Your Plugin

### 1. Simple sequence (manual timing)

```python
from video_automation.sequences.base import VideoSequence

class MyIntro(VideoSequence):
    name = "Introduction"
    sequence_id = "seq00"
    duration_estimate = 30.0
    obs_scene = "QGIS Fullscreen"

    def execute(self, obs, qgis, config):
        qgis.focus_qgis()
        qgis.click_at("my_button")
        qgis.wait(2.0)
        qgis.scroll_down(3)
```

### 2. Timeline sequence (narration-synchronized)

```python
from video_automation.sequences.base import TimelineSequence
from video_automation.core.timeline import NarrationCue

class MyDemo(TimelineSequence):
    name = "Live Demo"
    sequence_id = "seq01"
    duration_estimate = 60.0

    def build_timeline(self, obs, qgis, config):
        return [
            NarrationCue(
                text="Welcome to my plugin.",
                actions=lambda: qgis.wait(1.0),
                sync="during",
            ),
            NarrationCue(
                text="Let's open the settings.",
                actions=lambda: qgis.click_at("settings_button"),
                sync="after",
            ),
        ]
```

### 3. Register sequences

Create `my_project/sequences/__init__.py`:

```python
from video_automation.sequences.base import VideoSequence
# Import your sequence modules here to register them
from my_project.sequences.seq00_intro import MyIntro
from my_project.sequences.seq01_demo import MyDemo

SEQUENCES = [MyIntro, MyDemo]
```

Then run:
```bash
video-automation --list --sequences-package my_project.sequences
video-automation --all --sequences-package my_project.sequences
```

## Configuration

See `config.template.yaml` for all available options. Key sections:

| Section | Purpose |
|---------|---------|
| `obs` | OBS WebSocket connection, scenes, output directory |
| `qgis` | Window title, plugin panel name, calibrated UI positions |
| `timing` | Click/type/scroll delays, transition pauses |
| `diagrams` | Mermaid rendering (resolution, theme, colors) |
| `narration` | TTS engine, voice, speed, F5-TTS options |
| `capture` | Headless frame capture (FPS, resolution, display) |
| `output` | Final video encoding (resolution, fps, codec) |

## TTS Engines

| Engine | Cost | Quality | Setup |
|--------|------|---------|-------|
| edge-tts | Free | Good | `pip install edge-tts` |
| ElevenLabs | Paid | Excellent | `pip install elevenlabs` + API key |
| F5-TTS | Free | Excellent | Conda env + GPU recommended |

## Requirements

- Python 3.10+
- QGIS 3.22+ (with your plugin installed)
- FFmpeg (for video assembly)
- OBS Studio (desktop mode) or Docker (headless mode)

## License

MIT
