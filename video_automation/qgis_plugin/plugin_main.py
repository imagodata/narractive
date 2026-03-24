"""
Narractive QGIS Plugin — Main plugin class
==========================================
Installs a Dock panel in QGIS with controls to run the Narractive
video production pipeline from within QGIS.

Compatible with QGIS 3.28+ (LTR).

Install::

    narractive qgis-plugin install

Then restart QGIS and enable the plugin via Plugins → Manage plugins.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from qgis.PyQt.QtCore import Qt  # type: ignore
    from qgis.PyQt.QtWidgets import (  # type: ignore
        QAction,
        QComboBox,
        QDockWidget,
        QLabel,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
    from qgis.core import QgsProject  # type: ignore

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False


class NarractivePlugin:
    """Main plugin class registered with QGIS."""

    def __init__(self, iface) -> None:
        self.iface = iface
        self._dock: NarractiveDocPanel | None = None
        self._action: QAction | None = None  # type: ignore[name-defined]

    def initGui(self) -> None:  # noqa: N802
        """Called by QGIS when the plugin is loaded."""
        self._action = QAction("Narractive", self.iface.mainWindow())  # type: ignore[name-defined]
        self._action.setCheckable(True)
        self._action.triggered.connect(self._toggle_dock)
        self.iface.addToolBarIcon(self._action)
        self.iface.addPluginToMenu("&Narractive", self._action)

        self._dock = NarractiveDocPanel(self.iface)
        self.iface.mainWindow().addDockWidget(Qt.RightDockWidgetArea, self._dock)  # type: ignore[name-defined]
        self._dock.visibilityChanged.connect(self._action.setChecked)

    def unload(self) -> None:
        """Called by QGIS when the plugin is unloaded."""
        if self._action:
            self.iface.removePluginMenu("&Narractive", self._action)
            self.iface.removeToolBarIcon(self._action)
        if self._dock:
            self.iface.mainWindow().removeDockWidget(self._dock)
            self._dock.deleteLater()

    def _toggle_dock(self, checked: bool) -> None:
        if self._dock:
            self._dock.setVisible(checked)


class NarractiveDocPanel(QDockWidget):  # type: ignore[name-defined]
    """Dock panel with Narractive pipeline controls."""

    def __init__(self, iface) -> None:
        super().__init__("Narractive")
        self.iface = iface
        self.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea  # type: ignore[name-defined]
        )
        self._build_ui()

    def _build_ui(self) -> None:
        container = QWidget()  # type: ignore[name-defined]
        layout = QVBoxLayout(container)  # type: ignore[name-defined]
        layout.setSpacing(8)

        # Project info
        self._project_label = QLabel("Project: (none)")  # type: ignore[name-defined]
        self._project_label.setWordWrap(True)
        layout.addWidget(self._project_label)

        # Sequence selector
        layout.addWidget(QLabel("Sequence:"))  # type: ignore[name-defined]
        self._seq_combo = QComboBox()  # type: ignore[name-defined]
        self._refresh_sequences()
        layout.addWidget(self._seq_combo)

        # Buttons
        btn_refresh = QPushButton("Refresh sequences")  # type: ignore[name-defined]
        btn_refresh.clicked.connect(self._refresh_sequences)
        layout.addWidget(btn_refresh)

        self._btn_run = QPushButton("Run Narractive")  # type: ignore[name-defined]
        self._btn_run.clicked.connect(self._run_pipeline)
        layout.addWidget(self._btn_run)

        btn_narration = QPushButton("Generate narration only")  # type: ignore[name-defined]
        btn_narration.clicked.connect(self._run_narration)
        layout.addWidget(btn_narration)

        btn_assemble = QPushButton("Assemble video")  # type: ignore[name-defined]
        btn_assemble.clicked.connect(self._run_assemble)
        layout.addWidget(btn_assemble)

        # Log output
        layout.addWidget(QLabel("Log:"))  # type: ignore[name-defined]
        self._log = QPlainTextEdit()  # type: ignore[name-defined]
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(500)
        layout.addWidget(self._log)

        layout.addStretch()
        self.setWidget(container)

        try:
            QgsProject.instance().readProject.connect(self._on_project_changed)  # type: ignore[name-defined]
        except Exception:
            pass
        self._on_project_changed()

    def _on_project_changed(self) -> None:
        path = QgsProject.instance().fileName()  # type: ignore[name-defined]
        self._project_label.setText(f"Project: {path or '(none)'}")

    def _refresh_sequences(self) -> None:
        """Scan sequences/ folder and populate combo."""
        self._seq_combo.clear()
        self._seq_combo.addItem("(all)")
        sequences_dir = Path.cwd() / "sequences"
        if sequences_dir.exists():
            for f in sorted(sequences_dir.glob("seq*.py")):
                self._seq_combo.addItem(f.stem)
        self._log_msg(f"Sequences refreshed ({self._seq_combo.count() - 1} found)")

    def _run_pipeline(self) -> None:
        seq = self._seq_combo.currentText()
        if seq == "(all)":
            self._run_command(["narractive", "run", "--all"])
        else:
            self._run_command(["narractive", "run", "--sequence", seq])

    def _run_narration(self) -> None:
        self._run_command(["narractive", "run", "--narration"])

    def _run_assemble(self) -> None:
        self._run_command(["narractive", "run", "--assemble"])

    def _run_command(self, args: list[str]) -> None:
        self._log_msg(f"$ {' '.join(args)}")
        self._btn_run.setEnabled(False)
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                cwd=str(Path.cwd()),
                timeout=300,
            )
            if result.stdout:
                self._log_msg(result.stdout)
            if result.stderr:
                self._log_msg(result.stderr)
            if result.returncode != 0:
                self._log_msg(f"[ERROR] exit code {result.returncode}")
            else:
                self._log_msg("[DONE]")
        except subprocess.TimeoutExpired:
            self._log_msg("[TIMEOUT] Command timed out after 5 minutes")
        except FileNotFoundError:
            self._log_msg("[ERROR] 'narractive' not found — is it installed?")
        finally:
            self._btn_run.setEnabled(True)

    def _log_msg(self, msg: str) -> None:
        self._log.appendPlainText(msg.rstrip())
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )
