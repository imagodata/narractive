"""
QGIS Controller — Interface unifiée multi-mode
===============================================
Abstraction commune pour contrôler QGIS via différents backends :

- ``pyautogui``  : contrôle GUI via PyAutoGUI (comportement historique)
- ``pyqgis``     : appels natifs via :class:`~video_automation.core.qgis_bridge.QGISBridge`
- ``headless``   : rendu sans écran via :class:`~video_automation.core.qgis_headless.HeadlessRenderer`
- ``auto``       : détection automatique selon l'environnement

Usage::

    from video_automation.core.qgis_controller import create_controller

    ctrl = create_controller(config)     # lit config['qgis']['mode']
    ctrl.load_layer("my_data.gpkg")
    ctrl.render_map("output/scene_01.png")

Config YAML::

    qgis:
      mode: auto            # auto | pyautogui | pyqgis | headless
      prefix_path: /usr     # for headless / pyqgis bootstrap
      project_path: my_project.qgz   # required for headless render_map
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class QGISController(ABC):
    """
    Abstract interface for QGIS control backends.

    All concrete implementations expose the same high-level methods so that
    sequences can switch backends without code changes.
    """

    @abstractmethod
    def load_layer(self, path: str | Path, layer_name: str | None = None) -> Any:
        """Load a spatial layer into QGIS."""

    @abstractmethod
    def render_map(
        self,
        output_png: str | Path,
        extent: tuple[float, float, float, float] | None = None,
        size: tuple[int, int] = (1920, 1080),
    ) -> Path:
        """Render the current map view to a PNG file."""

    @abstractmethod
    def zoom_to_layer(self, layer_name: str) -> None:
        """Zoom the canvas to a layer's full extent."""

    @abstractmethod
    def select_features(self, layer_name: str, expression: str) -> int:
        """Select features by QGIS expression. Returns selected count."""

    @abstractmethod
    def run_algorithm(self, algorithm_id: str, params: dict) -> dict:
        """Run a QGIS processing algorithm."""

    def get_mode(self) -> str:
        """Return the controller's mode name."""
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# PyAutoGUI implementation (existing behaviour)
# ---------------------------------------------------------------------------


class AutoGUIController(QGISController):
    """Controls QGIS via PyAutoGUI mouse/keyboard simulation."""

    def __init__(self, config: dict) -> None:
        from video_automation.core.app_automator import AppAutomator  # type: ignore

        self._automator = AppAutomator(config)
        logger.info("QGISController: PyAutoGUI mode")

    def load_layer(self, path: str | Path, layer_name: str | None = None) -> Any:
        logger.warning("load_layer not supported in PyAutoGUI mode — no-op")
        return None

    def render_map(
        self,
        output_png: str | Path,
        extent: tuple[float, float, float, float] | None = None,
        size: tuple[int, int] = (1920, 1080),
    ) -> Path:
        output_png = Path(output_png)
        self._automator.capture_screenshot(str(output_png))
        return output_png

    def zoom_to_layer(self, layer_name: str) -> None:
        logger.warning("zoom_to_layer not supported in PyAutoGUI mode")

    def select_features(self, layer_name: str, expression: str) -> int:
        logger.warning("select_features not supported in PyAutoGUI mode")
        return 0

    def run_algorithm(self, algorithm_id: str, params: dict) -> dict:
        logger.warning("run_algorithm not supported in PyAutoGUI mode")
        return {}


# ---------------------------------------------------------------------------
# PyQGIS implementation
# ---------------------------------------------------------------------------


class PyQGISController(QGISController):
    """Controls QGIS via native PyQGIS API calls (requires running QGIS)."""

    def __init__(self, config: dict) -> None:
        from video_automation.core.qgis_bridge import QGISBridge  # type: ignore

        self._bridge = QGISBridge()
        self._config = config
        logger.info("QGISController: PyQGIS mode")

    def load_layer(self, path: str | Path, layer_name: str | None = None) -> Any:
        path = Path(path)
        raster_exts = {".tif", ".tiff", ".img", ".ecw", ".vrt", ".nc"}
        if path.suffix.lower() in raster_exts:
            return self._bridge.load_raster_layer(path, layer_name)
        return self._bridge.load_vector_layer(path, layer_name)

    def render_map(
        self,
        output_png: str | Path,
        extent: tuple[float, float, float, float] | None = None,
        size: tuple[int, int] = (1920, 1080),
    ) -> Path:
        from qgis.core import (  # type: ignore
            QgsMapRendererParallelJob,
            QgsMapSettings,
            QgsProject,
            QgsRectangle,
        )

        try:
            from qgis.PyQt.QtCore import QSize  # type: ignore
        except ImportError:
            from PyQt5.QtCore import QSize  # type: ignore

        output_png = Path(output_png)
        output_png.parent.mkdir(parents=True, exist_ok=True)

        settings = QgsMapSettings()
        settings.setLayers(list(QgsProject.instance().mapLayers().values()))
        settings.setOutputSize(QSize(*size))
        if extent:
            settings.setExtent(QgsRectangle(*extent))

        job = QgsMapRendererParallelJob(settings)
        job.start()
        job.waitForFinished()
        job.renderedImage().save(str(output_png), "PNG")
        return output_png

    def zoom_to_layer(self, layer_name: str) -> None:
        self._bridge.zoom_to_layer(layer_name)

    def select_features(self, layer_name: str, expression: str) -> int:
        return self._bridge.select_features(layer_name, expression)

    def run_algorithm(self, algorithm_id: str, params: dict) -> dict:
        return self._bridge.run_algorithm(algorithm_id, params)


# ---------------------------------------------------------------------------
# Headless implementation
# ---------------------------------------------------------------------------


class HeadlessController(QGISController):
    """Renders QGIS maps headlessly — no display required."""

    def __init__(self, config: dict) -> None:
        from video_automation.core.qgis_headless import HeadlessRenderer  # type: ignore

        qgis_cfg = config.get("qgis", {})
        self._renderer = HeadlessRenderer(prefix_path=qgis_cfg.get("prefix_path"))
        self._project_path: str | None = qgis_cfg.get("project_path")
        self._config = config
        logger.info("QGISController: Headless mode")

    def load_layer(self, path: str | Path, layer_name: str | None = None) -> Any:
        from video_automation.core.qgis_bridge import QGISBridge  # type: ignore

        bridge = QGISBridge()
        path = Path(path)
        raster_exts = {".tif", ".tiff", ".img", ".ecw", ".vrt", ".nc"}
        if path.suffix.lower() in raster_exts:
            return bridge.load_raster_layer(path, layer_name)
        return bridge.load_vector_layer(path, layer_name)

    def render_map(
        self,
        output_png: str | Path,
        extent: tuple[float, float, float, float] | None = None,
        size: tuple[int, int] = (1920, 1080),
    ) -> Path:
        if not self._project_path:
            raise ValueError(
                "qgis.project_path must be set in config.yaml for headless render_map"
            )
        return self._renderer.render(
            self._project_path, output_png, extent=extent, size=size
        )

    def zoom_to_layer(self, layer_name: str) -> None:
        logger.warning("zoom_to_layer not supported in headless mode")

    def select_features(self, layer_name: str, expression: str) -> int:
        logger.warning("select_features not supported in headless mode")
        return 0

    def run_algorithm(self, algorithm_id: str, params: dict) -> dict:
        from video_automation.core.qgis_bridge import QGISBridge  # type: ignore

        bridge = QGISBridge()
        return bridge.run_algorithm(algorithm_id, params)


# ---------------------------------------------------------------------------
# Auto-detection & factory
# ---------------------------------------------------------------------------


def _detect_mode() -> str:
    """
    Auto-detect the best QGIS control mode for the current environment.

    Priority:
    1. ``pyqgis``   — if running inside QGIS (iface available)
    2. ``headless`` — if PyQGIS is importable but no GUI
    3. ``pyautogui``— fallback
    """
    # Running inside QGIS?
    try:
        from qgis.utils import iface  # type: ignore

        if iface is not None:
            return "pyqgis"
    except ImportError:
        pass

    # PyQGIS available (headless)?
    try:
        import qgis.core  # type: ignore  # noqa: F401

        return "headless"
    except ImportError:
        pass

    return "pyautogui"


def create_controller(config: dict) -> QGISController:
    """
    Factory: create the appropriate :class:`QGISController` from *config*.

    Parameters
    ----------
    config : dict
        Full narractive config dict. Reads ``config['qgis']['mode']``.
        Valid values: ``auto`` (default), ``pyautogui``, ``pyqgis``, ``headless``.

    Returns
    -------
    QGISController

    Raises
    ------
    ValueError
        If an unknown mode is specified.
    """
    qgis_cfg = config.get("qgis", {})
    mode = qgis_cfg.get("mode", "auto")

    if mode == "auto":
        mode = _detect_mode()
        logger.info("QGIS mode auto-detected: %s", mode)

    if mode == "pyqgis":
        return PyQGISController(config)
    elif mode == "headless":
        return HeadlessController(config)
    elif mode == "pyautogui":
        return AutoGUIController(config)
    else:
        raise ValueError(
            f"Unknown QGIS mode: {mode!r}. Valid values: auto, pyqgis, headless, pyautogui"
        )
