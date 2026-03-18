"""
Video Automation — Desktop Application Video Production Framework
================================================================
A modular, reusable framework for automating demo videos of any
desktop application.

Core modules:
  - app_automator: PyAutoGUI-based UI control
  - obs_controller: OBS WebSocket 5.x recording
  - frame_capturer: Headless Xvfb frame capture (Docker)
  - narrator: Multi-engine TTS (edge-tts, ElevenLabs, F5-TTS)
  - timeline: Narration-synchronized cue execution
  - diagram_generator: Mermaid → HTML/PNG slides
  - video_assembler: FFmpeg post-production pipeline
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("narractive")
except PackageNotFoundError:
    try:
        __version__ = version("video-automation")
    except PackageNotFoundError:
        __version__ = "2.0.0"
