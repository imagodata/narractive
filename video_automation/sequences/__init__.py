"""
Video Sequences
===============
Each module implements one sequence from a video script.
Sequences are auto-discovered from this package and sorted by sequence_id.

To create sequences for your project, create a sub-package under this
directory (e.g. ``sequences/my_plugin/``) and import them in your CLI
entry point.
"""
from __future__ import annotations

from video_automation.sequences.base import TimelineSequence, VideoSequence

__all__ = ["VideoSequence", "TimelineSequence"]
