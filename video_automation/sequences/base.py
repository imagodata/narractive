"""
Base Video Sequence
===================
All sequence classes inherit from VideoSequence. The orchestrator calls
setup() -> execute() -> teardown() in order.

Works with both OBSController (desktop) and FrameCapturer (headless/Docker).
Both implement the same recording interface (start/stop/switch_scene).

For narration-synchronized sequences, use **TimelineSequence** instead.
Override ``build_timeline()`` to return a list of ``NarrationCue`` objects
that pair narration text with UI actions.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

if TYPE_CHECKING:
    from video_automation.core.app_automator import AppAutomator
    from video_automation.core.timeline import NarrationCue, TimelineResult


@runtime_checkable
class Recorder(Protocol):
    """Protocol that both OBSController and FrameCapturer implement."""

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def start_recording(self) -> None: ...
    def stop_recording(self) -> str | None: ...
    def pause_recording(self) -> None: ...
    def resume_recording(self) -> None: ...
    def wait_for_recording_start(self, timeout: float = ...) -> None: ...
    def switch_scene(self, scene_name: str) -> None: ...
    def get_current_scene(self) -> str: ...
    def show_diagram_overlay(self, visible: bool) -> None: ...
    def __enter__(self) -> Recorder: ...
    def __exit__(self, *args: object) -> None: ...


logger = logging.getLogger(__name__)


class VideoSequence(ABC):
    """
    Abstract base class for a single video sequence.

    Subclasses must set class attributes and implement execute().

    Attributes
    ----------
    name : str
        Human-readable name for this sequence.
    sequence_id : str
        Short identifier, e.g. "seq04".
    duration_estimate : float
        Estimated recording duration in seconds.
    narration_text : str
        Full narration text (used for TTS generation).
    diagram_ids : list[str]
        Which diagram IDs to show during this sequence.
    obs_scene : str
        OBS scene name to activate before recording this sequence.
    """

    name: str = "Unnamed Sequence"
    sequence_id: str = "seq00"
    duration_estimate: float = 30.0
    narration_text: str = ""
    diagram_ids: ClassVar[list[str]] = []
    obs_scene: str = "Main"

    # Populated after execution for TimelineSequence; always None for legacy.
    timeline_result: TimelineResult | None = None

    def __init__(self) -> None:
        self._start_time: float = 0.0
        self._log = logging.getLogger(f"sequences.{self.sequence_id}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup(self, obs: Recorder, app: AppAutomator, config: dict) -> None:
        """
        Called before recording starts. Switch scene, focus the app, etc.
        Override to add sequence-specific setup.
        """
        self._log.info("=== SETUP: %s ===", self.name)
        try:
            obs.switch_scene(self.obs_scene)
        except Exception as exc:
            self._log.warning("Scene switch failed: %s", exc)

        app.focus_app()
        transition_pause = config.get("timing", {}).get("transition_pause", 2.0)
        time.sleep(transition_pause)

    @abstractmethod
    def execute(self, obs: Recorder, app: AppAutomator, config: dict) -> None:
        """
        Main automation steps for this sequence.
        Must be implemented by each subclass.
        """
        ...

    def teardown(self, obs: Recorder, app: AppAutomator, config: dict) -> None:
        """
        Called after the sequence finishes. Pause before next sequence.
        Override if cleanup is needed.
        """
        transition_pause = config.get("timing", {}).get("transition_pause", 2.0)
        self._log.info("=== TEARDOWN: %s (%.1fs elapsed) ===", self.name, self.elapsed())
        time.sleep(transition_pause)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def run(self, obs: Recorder, app: AppAutomator, config: dict) -> None:
        """Run the full sequence: setup -> execute -> teardown."""
        self._start_time = time.time()
        self._log.info("Starting sequence: %s", self.name)
        try:
            self.setup(obs, app, config)
            self.execute(obs, app, config)
        finally:
            self.teardown(obs, app, config)

    def elapsed(self) -> float:
        """Return elapsed seconds since sequence started."""
        return time.time() - self._start_time if self._start_time else 0.0

    def edit_config_value(
        self,
        app: AppAutomator,
        config: dict,
        region_name: str,
        value: str,
    ) -> bool:
        """Double-click a config field, clear it, type *value* and confirm."""
        import pyautogui

        region = config["app"]["regions"].get(region_name)
        if not region:
            self._log.warning("%s not calibrated -- skipping", region_name)
            return False
        move_dur = config["timing"].get("mouse_move_duration", 0.5)
        pyautogui.click(region["x"], region["y"], duration=move_dur)
        app.wait(0.3)
        pyautogui.doubleClick(region["x"], region["y"])
        app.wait(0.3)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.typewrite(value, interval=0.06)
        pyautogui.press("return")
        app.wait(0.5)
        return True

    def show_diagram_and_return(
        self,
        obs: Recorder,
        app: AppAutomator,
        diagram_id: str,
        duration: float = 5.0,
    ) -> None:
        """Show a diagram overlay then return focus to the side panel."""
        self.show_diagram(obs, diagram_id, duration=duration)
        app.focus_panel()
        app.wait(0.5)

    def show_diagram(self, obs: Recorder, diagram_id: str, duration: float = 5.0) -> None:
        """Switch to the Diagram Overlay scene, wait, then switch back."""
        self._log.info("Showing diagram: %s for %.1fs", diagram_id, duration)
        obs.show_diagram_overlay(visible=True)
        time.sleep(duration)
        obs.show_diagram_overlay(visible=False)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} est={self.duration_estimate:.0f}s>"


class TimelineSequence(VideoSequence):
    """
    A video sequence driven by narration-synchronized cues.

    Instead of implementing ``execute()`` with manual ``wait()`` calls,
    subclasses override ``build_timeline()`` to return a list of
    ``NarrationCue`` objects.  The timeline executor handles timing
    automatically based on actual narration audio durations.

    Attributes
    ----------
    play_audio : bool
        If True, play narration through speakers during recording.
    timeline_result : TimelineResult or None
        Populated after execute(); contains timecodes for assembly.
    """

    play_audio: bool = False

    def build_timeline(
        self,
        obs: Recorder,
        app: AppAutomator,
        config: dict,
    ) -> list[NarrationCue]:
        """
        Build the list of narration cues for this sequence.
        Override this method instead of ``execute()``.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement build_timeline()")

    def execute(self, obs: Recorder, app: AppAutomator, config: dict) -> None:
        """Execute the timeline: prepare narration audio, then run cues."""
        from video_automation.core.narrator import Narrator
        from video_automation.core.timeline import TimelineExecutor

        cues = self.build_timeline(obs, app, config)
        if not cues:
            self._log.warning("No cues defined for %s", self.name)
            return

        narr_config = config.get("narration", {})
        narrator = Narrator(narr_config)

        video_id = self.sequence_id.split("_")[0] if "_" in self.sequence_id else ""
        cache_dir = narrator.output_dir
        if video_id:
            cache_dir = cache_dir / video_id / "segments"

        executor = TimelineExecutor(
            narrator=narrator,
            sequence_id=self.sequence_id,
            cache_dir=cache_dir,
            play_audio=self.play_audio,
        )

        executor.prepare(cues)

        estimated = executor.get_total_estimated_duration(cues)
        self._log.info(
            "%s: %d cues, ~%.0fs estimated",
            self.name,
            len(cues),
            estimated,
        )

        self.timeline_result = executor.execute(cues, obs=obs)
        self._log.info(
            "%s complete: %.1fs actual",
            self.name,
            self.timeline_result.total_duration,
        )
