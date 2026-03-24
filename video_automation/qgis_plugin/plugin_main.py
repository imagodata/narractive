"""
Narractive QGIS Plugin — Main plugin class and dock panel
==========================================================
Provides a QDockWidget docked panel inside QGIS with controls to:

* Run the full video production pipeline
* Generate TTS narration audio
* Assemble the final video
* View pipeline logs
* Select and restore map snapshots

Requirements: QGIS 3.28+, PyQGIS, PyQt5.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conditional Qt / QGIS imports (only available inside QGIS)
# ---------------------------------------------------------------------------

try:
    from qgis.PyQt.QtCore import Qt  # type: ignore
    from qgis.PyQt.QtWidgets import (  # type: ignore
        QAction,
        QComboBox,
        QDockWidget,
        QHBoxLayout,
        QLabel,
        QPlainTextEdit,
        QPushButton,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )
    from qgis.core import QgsMessageLog, Qgis  # type: ignore

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------


class NarractivePlugin:
    """
    Main QGIS plugin class.

    Registered with QGIS via :func:`classFactory` in ``__init__.py``.
    """

    PLUGIN_NAME = "Narractive"

    def __init__(self, iface: Any) -> None:
        """
        Parameters
        ----------
        iface : QgisInterface
            The QGIS interface object.
        """
        self.iface = iface
        self._dock: "NarractiveDocPanel | None" = None
        self._action: Any = None

    # ------------------------------------------------------------------
    # QGIS plugin lifecycle
    # ------------------------------------------------------------------

    def initGui(self) -> None:  # noqa: N802 — QGIS naming convention
        """Called by QGIS when the plugin is loaded. Creates UI elements."""
        if not _QT_AVAILABLE:
            logger.warning("Narractive: Qt/QGIS not available, plugin UI disabled.")
            return

        # Toolbar action to toggle the dock panel
        self._action = QAction(self.PLUGIN_NAME, self.iface.mainWindow())
        self._action.setCheckable(True)
        self._action.setToolTip("Toggle Narractive video pipeline panel")
        self._action.triggered.connect(self._toggle_dock)
        self.iface.addToolBarIcon(self._action)
        self.iface.addPluginToMenu(self.PLUGIN_NAME, self._action)

        # Create and add the dock panel
        self._dock = NarractiveDocPanel(self.iface)
        self.iface.mainWindow().addDockWidget(Qt.RightDockWidgetArea, self._dock)
        self._dock.visibilityChanged.connect(self._action.setChecked)

    def unload(self) -> None:
        """Called by QGIS when the plugin is unloaded. Cleans up UI elements."""
        if not _QT_AVAILABLE:
            return
        if self._action:
            self.iface.removeToolBarIcon(self._action)
            self.iface.removePluginMenu(self.PLUGIN_NAME, self._action)
        if self._dock:
            self.iface.mainWindow().removeDockWidget(self._dock)
            self._dock.deleteLater()
            self._dock = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _toggle_dock(self, checked: bool) -> None:
        if self._dock:
            self._dock.setVisible(checked)


# ---------------------------------------------------------------------------
# Dock panel
# ---------------------------------------------------------------------------


class NarractiveDocPanel(QDockWidget):
    """
    Dockable panel for the Narractive video pipeline.

    Contains:
    * "Run pipeline" button
    * "Generate narration" button
    * "Assemble video" button
    * Snapshot selector (combo box) + "Restore snapshot" button
    * Log output area
    """

    def __init__(self, iface: Any, parent: Any = None) -> None:
        super().__init__("Narractive", parent)
        self.iface = iface
        self.setObjectName("NarractiveDocPanel")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._build_ui()
        self._refresh_snapshots()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        container = QWidget()
        self.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Title label
        title = QLabel("<b>Narractive Pipeline</b>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # --- Pipeline buttons ---
        self._btn_run = QPushButton("Run pipeline")
        self._btn_run.setToolTip("Run the complete Narractive video production pipeline")
        self._btn_run.clicked.connect(self._on_run_pipeline)
        layout.addWidget(self._btn_run)

        self._btn_narration = QPushButton("Generate narration")
        self._btn_narration.setToolTip("Generate TTS narration audio for all sequences")
        self._btn_narration.clicked.connect(self._on_generate_narration)
        layout.addWidget(self._btn_narration)

        self._btn_assemble = QPushButton("Assemble video")
        self._btn_assemble.setToolTip("Assemble final video from recorded clips")
        self._btn_assemble.clicked.connect(self._on_assemble_video)
        layout.addWidget(self._btn_assemble)

        # --- Snapshot controls ---
        snap_label = QLabel("Snapshots:")
        layout.addWidget(snap_label)

        snap_row = QHBoxLayout()
        self._combo_snapshots = QComboBox()
        self._combo_snapshots.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        self._combo_snapshots.setToolTip("Available map snapshots")
        snap_row.addWidget(self._combo_snapshots)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setFixedWidth(60)
        btn_refresh.clicked.connect(self._refresh_snapshots)
        snap_row.addWidget(btn_refresh)
        layout.addLayout(snap_row)

        self._btn_restore = QPushButton("Restore snapshot")
        self._btn_restore.setToolTip("Restore the selected map snapshot")
        self._btn_restore.clicked.connect(self._on_restore_snapshot)
        layout.addWidget(self._btn_restore)

        # --- Log output ---
        log_label = QLabel("Log:")
        layout.addWidget(log_label)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(500)
        self._log.setPlaceholderText("Pipeline output will appear here…")
        layout.addWidget(self._log)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_run_pipeline(self) -> None:
        self._log_message("Starting pipeline…")
        self._run_narractive_cmd(["--all"])

    def _on_generate_narration(self) -> None:
        self._log_message("Generating narration…")
        self._run_narractive_cmd(["--narration"])

    def _on_assemble_video(self) -> None:
        self._log_message("Assembling video…")
        self._run_narractive_cmd(["--assemble"])

    def _on_restore_snapshot(self) -> None:
        name = self._combo_snapshots.currentText()
        if not name:
            self._log_message("No snapshot selected.")
            return
        self._log_message(f"Restoring snapshot: {name}")
        try:
            from video_automation.core.qgis_snapshot import QGISSnapshot

            snap_dir = QGISSnapshot.snapshot_dir()
            snap_path = snap_dir / f"{name}.json"
            snap = QGISSnapshot.load(snap_path)
            snap.restore()
            self._log_message(f"Snapshot '{name}' restored.")
        except Exception as exc:
            self._log_message(f"Error restoring snapshot: {exc}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_snapshots(self) -> None:
        """Repopulate the snapshot combo from the snapshots directory."""
        from video_automation.core.qgis_snapshot import QGISSnapshot

        self._combo_snapshots.clear()
        snapshots = QGISSnapshot.list_snapshots()
        for p in snapshots:
            self._combo_snapshots.addItem(p.stem)
        if not snapshots:
            self._combo_snapshots.addItem("(no snapshots)")

    def _run_narractive_cmd(self, extra_args: list[str]) -> None:
        """Run a ``narractive`` CLI command in a subprocess and log output."""
        cmd = [sys.executable, "-m", "video_automation"] + extra_args
        self._log_message(f"$ {' '.join(cmd)}")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(Path.cwd()),
            )
            for line in proc.stdout:  # type: ignore[union-attr]
                self._log_message(line.rstrip())
            proc.wait()
            if proc.returncode != 0:
                self._log_message(f"[exit code {proc.returncode}]")
        except Exception as exc:
            self._log_message(f"Error: {exc}")

    def _log_message(self, message: str) -> None:
        """Append *message* to the log panel and QGIS message log."""
        self._log.appendPlainText(message)
        if _QT_AVAILABLE:
            try:
                QgsMessageLog.logMessage(message, "Narractive", Qgis.Info)
            except Exception:
                pass
