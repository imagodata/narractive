"""
QGIS Controller — Unified ABC + factory for QGIS automation backends
=====================================================================
Defines the :class:`QGISController` abstract base class and three
concrete implementations:

* :class:`AutoGUIController` — drives QGIS via PyAutoGUI (desktop GUI)
* :class:`PyQGISController`  — direct Python API via :class:`~.qgis_bridge.QGISBridge`
* :class:`HeadlessController` — headless PNG rendering via :class:`~.qgis_headless.HeadlessRenderer`

Factory function::

    from video_automation.core.qgis_controller import create_controller

    ctrl = create_controller(config)
    ctrl.load_layer("/data/roads.shp", "roads")

The backend is selected from ``config['qgis']['mode']``:

``auto``
    Detected automatically: ``pyqgis`` if PyQGIS is importable, else
    ``pyautogui``.
``pyautogui``
    Always use PyAutoGUI.
``pyqgis``
    Always use the PyQGIS API directly.
``headless``
    Render maps without a display.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class QGISController(ABC):
    """
    Abstract interface for QGIS automation backends.

    Concrete subclasses must implement all abstract methods below.
    """

    @abstractmethod
    def load_layer(self, path: str, name: str) -> Any:
        """
        Load a spatial layer into the QGIS session.

        Parameters
        ----------
        path:
            File path or URI to the layer data source.
        name:
            Display name for the layer.

        Returns
        -------
        Any
            Backend-specific layer handle or None.
        """

    @abstractmethod
    def render_map(self, output_path: str, **kwargs: Any) -> str:
        """
        Capture or render the current map view to an image file.

        Parameters
        ----------
        output_path:
            Destination file path (PNG).

        Returns
        -------
        str
            The path to the written file.
        """

    @abstractmethod
    def zoom_to_layer(self, layer: Any) -> None:
        """
        Zoom the map canvas to the extent of *layer*.

        Parameters
        ----------
        layer:
            Layer handle as returned by :meth:`load_layer`.
        """

    @abstractmethod
    def select_features(self, layer: Any, expression: str) -> int:
        """
        Select features in *layer* that match *expression*.

        Parameters
        ----------
        layer:
            Layer handle as returned by :meth:`load_layer`.
        expression:
            QGIS expression string.

        Returns
        -------
        int
            Number of features selected.
        """

    @abstractmethod
    def run_algorithm(self, algorithm_id: str, parameters: dict) -> dict:
        """
        Execute a QGIS Processing algorithm.

        Parameters
        ----------
        algorithm_id:
            Full algorithm ID, e.g. ``"native:buffer"``.
        parameters:
            Algorithm parameter dictionary.

        Returns
        -------
        dict
            Result dictionary.
        """


# ---------------------------------------------------------------------------
# Concrete implementations
# ---------------------------------------------------------------------------


class AutoGUIController(QGISController):
    """
    QGIS controller that drives the desktop application via PyAutoGUI.

    Suitable for capturing real screen recordings of QGIS interactions.
    """

    def __init__(self, config: dict | None = None) -> None:
        self._config = config or {}
        try:
            import pyautogui  # type: ignore  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "pyautogui is required for AutoGUIController. "
                "Install it with: pip install pyautogui"
            ) from exc
        logger.debug("AutoGUIController initialised")

    def load_layer(self, path: str, name: str) -> None:
        """Placeholder: layer loading via GUI automation is project-specific."""
        logger.info("[AutoGUI] load_layer(%r, %r) — implement via GUI macros", path, name)
        return None

    def render_map(self, output_path: str, **kwargs: Any) -> str:
        """Take a screenshot of the QGIS map canvas region."""
        import pyautogui  # type: ignore

        region = self._config.get("canvas_region")
        if region:
            screenshot = pyautogui.screenshot(region=tuple(region))
        else:
            screenshot = pyautogui.screenshot()
        screenshot.save(output_path)
        logger.info("[AutoGUI] Screenshot saved to %s", output_path)
        return output_path

    def zoom_to_layer(self, layer: Any) -> None:
        """Placeholder: zoom via GUI automation is application-specific."""
        logger.info("[AutoGUI] zoom_to_layer — implement via GUI macros")

    def select_features(self, layer: Any, expression: str) -> int:
        """Placeholder: feature selection via GUI automation."""
        logger.info("[AutoGUI] select_features(%r) — implement via GUI macros", expression)
        return 0

    def run_algorithm(self, algorithm_id: str, parameters: dict) -> dict:
        """Placeholder: algorithm execution via GUI automation."""
        logger.info("[AutoGUI] run_algorithm(%r) — implement via GUI macros", algorithm_id)
        return {}


class PyQGISController(QGISController):
    """
    QGIS controller using the direct PyQGIS Python API via :class:`QGISBridge`.

    Requires a running QGIS session with ``qgis.core`` available.
    """

    def __init__(self, config: dict | None = None) -> None:
        from video_automation.core.qgis_bridge import QGISBridge  # noqa: F401 — validates import

        self._config = config or {}
        self._bridge = QGISBridge()
        logger.debug("PyQGISController initialised")

    def load_layer(self, path: str, name: str) -> Any:
        return self._bridge.load_vector_layer(path, name)

    def render_map(self, output_path: str, **kwargs: Any) -> str:
        """Render via map canvas save (requires iface)."""
        try:
            from qgis.utils import iface  # type: ignore
        except ImportError as exc:
            raise ImportError("iface not available for render_map") from exc
        iface.mapCanvas().saveAsImage(output_path)
        logger.info("[PyQGIS] Map saved to %s", output_path)
        return output_path

    def zoom_to_layer(self, layer: Any) -> None:
        self._bridge.zoom_to_layer(layer)

    def select_features(self, layer: Any, expression: str) -> int:
        return self._bridge.select_features(layer, expression)

    def run_algorithm(self, algorithm_id: str, parameters: dict) -> dict:
        return self._bridge.run_algorithm(algorithm_id, parameters)


class HeadlessController(QGISController):
    """
    QGIS controller for headless (no-display) rendering via :class:`HeadlessRenderer`.

    Suitable for CI/CD pipelines and Docker environments.
    """

    def __init__(self, config: dict | None = None) -> None:
        from video_automation.core.qgis_headless import HeadlessRenderer  # validates import

        self._config = config or {}
        prefix = self._config.get("prefix_path")
        self._renderer = HeadlessRenderer(prefix_path=prefix)
        self._project_path: str | None = self._config.get("project_path")
        logger.debug("HeadlessController initialised")

    def load_layer(self, path: str, name: str) -> dict:
        """In headless mode, layer info is recorded for the next render call."""
        entry = {"path": path, "name": name}
        logger.info("[Headless] Recorded layer %r -> %r", name, path)
        return entry

    def render_map(self, output_path: str, **kwargs: Any) -> str:
        if not self._project_path:
            raise ValueError(
                "project_path must be set in config['qgis']['project_path'] "
                "for HeadlessController.render_map()"
            )
        extent = kwargs.get("extent")
        size = kwargs.get("size", (1920, 1080))
        dpi = kwargs.get("dpi", 96)
        self._renderer.render(
            self._project_path, output_path, extent=extent, size=size, dpi=dpi
        )
        return output_path

    def zoom_to_layer(self, layer: Any) -> None:
        """No-op in headless mode — extent is set at render time."""
        logger.debug("[Headless] zoom_to_layer — no-op in headless mode")

    def select_features(self, layer: Any, expression: str) -> int:
        """Feature selection is not meaningful in pure headless render mode."""
        logger.debug("[Headless] select_features — no-op in headless mode")
        return 0

    def run_algorithm(self, algorithm_id: str, parameters: dict) -> dict:
        """Processing algorithms require a full QgsApplication; use PyQGISController."""
        raise NotImplementedError(
            "run_algorithm is not supported by HeadlessController. "
            "Use PyQGISController or AutoGUIController."
        )


# ---------------------------------------------------------------------------
# Mode detection & factory
# ---------------------------------------------------------------------------


def _detect_mode() -> str:
    """
    Auto-detect the best available QGIS controller mode.

    Returns
    -------
    str
        ``"pyqgis"`` if PyQGIS is importable, else ``"pyautogui"``.
    """
    try:
        import qgis.core  # type: ignore  # noqa: F401
        return "pyqgis"
    except ImportError:
        return "pyautogui"


def create_controller(config: dict | None = None) -> QGISController:
    """
    Factory function that instantiates the appropriate :class:`QGISController`.

    Parameters
    ----------
    config:
        The full narractive config dict (as loaded from ``config.yaml``).
        The relevant section is ``config['qgis']``:

        .. code-block:: yaml

            qgis:
              mode: auto          # auto | pyautogui | pyqgis | headless
              prefix_path: /usr   # QGIS installation prefix (headless/pyqgis)
              project_path: null  # Default project for headless rendering

    Returns
    -------
    QGISController
        An initialised controller instance.

    Raises
    ------
    ValueError
        If an unknown mode is specified.
    """
    cfg = (config or {}).get("qgis", {})
    mode = cfg.get("mode", "auto")

    if mode == "auto":
        mode = _detect_mode()
        logger.debug("Auto-detected QGIS mode: %s", mode)

    if mode == "pyautogui":
        return AutoGUIController(config=cfg)
    elif mode == "pyqgis":
        return PyQGISController(config=cfg)
    elif mode == "headless":
        return HeadlessController(config=cfg)
    else:
        raise ValueError(
            f"Unknown QGIS controller mode: {mode!r}. "
            "Valid modes: auto, pyautogui, pyqgis, headless."
        )
