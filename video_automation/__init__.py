"""
Video Automation — QGIS Plugin Video Production Framework
==========================================================
A modular, reusable framework for automating QGIS plugin demo videos.

Core modules:
  - qgis_automator: PyAutoGUI-based QGIS control
  - obs_controller: OBS WebSocket 5.x recording
  - frame_capturer: Headless Xvfb frame capture (Docker)
  - narrator: Multi-engine TTS (edge-tts, ElevenLabs, F5-TTS)
  - timeline: Narration-synchronized cue execution
  - diagram_generator: Mermaid → HTML/PNG slides
  - video_assembler: FFmpeg post-production pipeline
"""

__version__ = "1.0.0"
