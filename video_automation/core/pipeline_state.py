"""
Pipeline State — Persistent Run State for Resume Support
=========================================================
Tracks which sequences have completed, failed, or are pending in a JSON
sidecar file so an interrupted ``narractive --all`` run can be resumed
automatically with ``narractive --all --resume``.

State file location: ``output/.narractive-state.json`` (configurable).

Usage::

    from video_automation.core.pipeline_state import PipelineState

    state = PipelineState.load("output/.narractive-state.json")
    state.start_run(sequences_package="my_project.sequences", total=11)

    state.mark_completed("seq00", recording_path="output/obs/seq00.mkv")
    state.mark_failed("seq01", error="TimeoutError: OBS did not respond")
    state.save()

    # On next invocation with --resume:
    state = PipelineState.load("output/.narractive-state.json")
    resume_from = state.resume_from_index()   # index of first non-completed seq
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default state file relative to the working directory
DEFAULT_STATE_FILE = "output/.narractive-state.json"

# Sequence status constants
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class PipelineState:
    """
    Persists and queries the execution state of a pipeline run.

    Parameters
    ----------
    state_file : Path
        Path to the JSON state file.
    """

    def __init__(self, state_file: Path) -> None:
        self.state_file = Path(state_file)
        self._data: dict = {}

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, state_file: str | Path = DEFAULT_STATE_FILE) -> "PipelineState":
        """
        Load state from *state_file*, or return a blank state if it does not exist.

        Parameters
        ----------
        state_file : str | Path
            Path to the JSON state file.
        """
        path = Path(state_file)
        instance = cls(path)

        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    instance._data = json.load(f)
                logger.info("Pipeline state loaded from %s", path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read pipeline state (%s): %s — starting fresh", path, exc)
                instance._data = {}
        else:
            logger.debug("No pipeline state file found at %s — starting fresh", path)

        return instance

    @classmethod
    def from_config(cls, config: dict) -> "PipelineState":
        """
        Create a :class:`PipelineState` using the ``output.state_file`` config key.

        Falls back to :data:`DEFAULT_STATE_FILE` when the key is absent.
        """
        state_file = config.get("output", {}).get("state_file", DEFAULT_STATE_FILE)
        return cls.load(state_file)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Write the current state to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            logger.debug("Pipeline state saved to %s", self.state_file)
        except OSError as exc:
            logger.warning("Failed to save pipeline state: %s", exc)

    def delete(self) -> None:
        """Delete the state file (--reset behaviour)."""
        if self.state_file.exists():
            self.state_file.unlink()
            logger.info("Pipeline state deleted: %s", self.state_file)
        self._data = {}

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    def start_run(
        self,
        sequences_package: Optional[str] = None,
        total: int = 0,
    ) -> None:
        """
        Initialise state for a new pipeline run.

        Parameters
        ----------
        sequences_package : str | None
            Dotted package path for the sequences being run.
        total : int
            Total number of sequences in the run.
        """
        now = datetime.now(timezone.utc).isoformat()
        self._data = {
            "run_id": now,
            "sequences_package": sequences_package or "",
            "total": total,
            "started_at": now,
            "updated_at": now,
            "sequences": {},
            "recordings": {},
        }

    def _ensure_run(self) -> None:
        if not self._data:
            self.start_run()

    # ------------------------------------------------------------------
    # Sequence status tracking
    # ------------------------------------------------------------------

    def mark_running(self, seq_id: str) -> None:
        """Mark *seq_id* as currently running."""
        self._ensure_run()
        self._data["sequences"][seq_id] = {
            "status": STATUS_RUNNING,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()

    def mark_completed(self, seq_id: str, recording_path: Optional[str] = None) -> None:
        """
        Mark *seq_id* as successfully completed.

        Parameters
        ----------
        seq_id : str
            Sequence identifier (e.g. ``"seq00"``).
        recording_path : str | None
            Path to the recorded video clip, if any.
        """
        self._ensure_run()
        entry: dict = {
            "status": STATUS_COMPLETED,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        if recording_path:
            entry["recording"] = str(recording_path)
            self._data["recordings"][seq_id] = str(recording_path)
        self._data["sequences"][seq_id] = entry
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()

    def mark_failed(self, seq_id: str, error: Optional[str] = None) -> None:
        """
        Mark *seq_id* as failed.

        Parameters
        ----------
        seq_id : str
            Sequence identifier.
        error : str | None
            Short description of the error, for display in ``narractive --status``.
        """
        self._ensure_run()
        entry: dict = {
            "status": STATUS_FAILED,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        if error:
            entry["error"] = str(error)[:512]
        self._data["sequences"][seq_id] = entry
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_completed(self, seq_id: str) -> bool:
        """Return ``True`` if *seq_id* completed successfully."""
        return self._data.get("sequences", {}).get(seq_id, {}).get("status") == STATUS_COMPLETED

    def completed_ids(self) -> list[str]:
        """Return a sorted list of completed sequence IDs."""
        return sorted(
            sid
            for sid, info in self._data.get("sequences", {}).items()
            if info.get("status") == STATUS_COMPLETED
        )

    def failed_ids(self) -> list[str]:
        """Return a sorted list of failed sequence IDs."""
        return sorted(
            sid
            for sid, info in self._data.get("sequences", {}).items()
            if info.get("status") == STATUS_FAILED
        )

    def pending_ids(self, all_seq_ids: list[str]) -> list[str]:
        """
        Return sequence IDs from *all_seq_ids* that are not yet completed.

        Parameters
        ----------
        all_seq_ids : list[str]
            Ordered list of all sequence IDs in the pipeline.
        """
        completed = set(self.completed_ids())
        return [sid for sid in all_seq_ids if sid not in completed]

    def resume_from_index(self, all_seq_ids: list[str]) -> int:
        """
        Return the index in *all_seq_ids* from which to resume.

        This is the index of the first sequence that is **not** completed.
        Returns ``0`` when there is no existing state (fresh start).

        Parameters
        ----------
        all_seq_ids : list[str]
            Ordered list of all sequence IDs (matching the run order).
        """
        completed = set(self.completed_ids())
        for i, sid in enumerate(all_seq_ids):
            if sid not in completed:
                return i
        return len(all_seq_ids)  # all done

    def get_recordings(self) -> dict[str, str]:
        """Return the ``{seq_id: recording_path}`` mapping."""
        return dict(self._data.get("recordings", {}))

    # ------------------------------------------------------------------
    # Pretty display
    # ------------------------------------------------------------------

    def status_table(self, all_seq_ids: Optional[list[str]] = None) -> str:
        """
        Return a human-readable status table.

        Parameters
        ----------
        all_seq_ids : list[str] | None
            Ordered list of all sequence IDs.  When ``None``, only the
            sequences recorded in state are shown.
        """
        seqs = self._data.get("sequences", {})
        if all_seq_ids is None:
            all_seq_ids = sorted(seqs.keys())

        if not all_seq_ids:
            return "(no pipeline state found)"

        icon = {
            STATUS_COMPLETED: "ok",
            STATUS_FAILED: "FAIL",
            STATUS_RUNNING: "...",
            STATUS_PENDING: "    ",
        }

        run_id = self._data.get("run_id", "unknown")
        pkg = self._data.get("sequences_package", "")
        lines = [
            f"Pipeline State — run {run_id}",
            f"Package: {pkg}" if pkg else "",
            "-" * 50,
            f"  {'Status':<8}  {'Sequence ID':<20}  {'Info'}",
            "-" * 50,
        ]

        for sid in all_seq_ids:
            info = seqs.get(sid, {})
            status = info.get("status", STATUS_PENDING)
            mark = icon.get(status, "?")
            extra = ""
            if status == STATUS_FAILED:
                extra = f"  ERROR: {info.get('error', '')}"
            elif status == STATUS_COMPLETED and "recording" in info:
                extra = f"  -> {Path(info['recording']).name}"
            lines.append(f"  [{mark:<4}]  {sid:<20}  {extra}")

        completed = len(self.completed_ids())
        failed = len(self.failed_ids())
        total = len(all_seq_ids)
        lines += [
            "-" * 50,
            f"  {completed}/{total} completed, {failed} failed",
        ]
        return "\n".join(l for l in lines if l != "")

    # ------------------------------------------------------------------
    # Serialization (for --json output)
    # ------------------------------------------------------------------

    def to_dict(self, all_seq_ids: Optional[list[str]] = None) -> dict:
        """Return the state as a plain dict (suitable for JSON serialisation)."""
        seqs = self._data.get("sequences", {})
        if all_seq_ids is None:
            all_seq_ids = list(seqs.keys())

        result = dict(self._data)
        result["completed"] = self.completed_ids()
        result["failed"] = self.failed_ids()
        result["pending"] = self.pending_ids(all_seq_ids)
        return result
