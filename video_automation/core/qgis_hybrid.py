"""
QGIS Hybrid Controller
======================
Combines PyQGIS API operations with PyAutoGUI mouse positioning.

Use this controller when you need to:

* Manipulate QGIS programmatically (load layers, run algorithms, select
  features) **and** guide the viewer's eye by moving the mouse to relevant
  screen locations — all in the same sequence step.

Typical use-case — tutorial video::

    ctrl = HybridController(config)

    # Load layer via API, then move mouse to the layer in the Layers panel
    layer = ctrl.load_layer_and_point("/data/communes.shp", "Communes")

    # Zoom to extent and point at map centre
    ctrl.zoom_to_layer_and_point(layer)

    # Highlight a geographic point on the map canvas
    ctrl.point_at_map_coordinate(2.3488, 48.8534)   # Paris, WGS84

Geo → screen conversion
-----------------------
:meth:`point_at_map_coordinate` converts a geographic coordinate (in the
project CRS) to absolute screen pixels using the map canvas region defined
in ``config['qgis']['canvas_region']``::

    qgis:
      canvas_region:
        x: 320        # left edge of the canvas in screen pixels
        y: 60         # top edge
        width: 1280
        height: 900

The mapping is a simple bi-linear interpolation against the current
``iface.mapCanvas().extent()``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class HybridController:
    """
    PyQGIS API + PyAutoGUI mouse positioning, combined in one controller.

    Parameters
    ----------
    config:
        Full narractive config dict.  The relevant sub-keys are:

        ``config['qgis']['canvas_region']``
            Dict with ``x``, ``y``, ``width``, ``height`` — absolute screen
            coordinates of the QGIS map canvas.  Required for
            :meth:`point_at_map_coordinate`.

        ``config['qgis']['prefix_path']``
            QGIS installation prefix (optional, passed to QgsApplication).

        All other keys under ``config['app']`` / ``config['timing']`` are
        forwarded to :class:`~video_automation.core.app_automator.AppAutomator`.
    """

    def __init__(self, config: dict | None = None) -> None:
        from video_automation.core.qgis_bridge import QGISBridge
        from video_automation.core.app_automator import AppAutomator

        self._config = config or {}
        self._qgis_cfg: dict = self._config.get("qgis", {})
        self._canvas_region: dict | None = self._qgis_cfg.get("canvas_region")

        self._bridge = QGISBridge()
        self._automator = AppAutomator(self._config)

        logger.debug(
            "HybridController initialised (canvas_region=%s)",
            self._canvas_region is not None,
        )

    # ------------------------------------------------------------------
    # QGISController interface (PyQGIS API)
    # ------------------------------------------------------------------

    def load_layer(self, path: str, name: str) -> Any:
        """Load a vector layer via PyQGIS API."""
        return self._bridge.load_vector_layer(path, name)

    def render_map(self, output_path: str, **kwargs: Any) -> str:
        """Render the current map canvas to a PNG via iface.mapCanvas()."""
        try:
            from qgis.utils import iface  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "iface is not available — run inside a QGIS session."
            ) from exc
        iface.mapCanvas().saveAsImage(output_path)
        logger.info("[Hybrid] Map rendered to %s", output_path)
        return output_path

    def zoom_to_layer(self, layer: Any) -> None:
        """Zoom the map canvas to the layer extent via PyQGIS."""
        self._bridge.zoom_to_layer(layer)

    def select_features(self, layer: Any, expression: str) -> int:
        """Select features matching *expression* via PyQGIS."""
        return self._bridge.select_features(layer, expression)

    def run_algorithm(self, algorithm_id: str, parameters: dict) -> dict:
        """Run a QGIS Processing algorithm via PyQGIS."""
        return self._bridge.run_algorithm(algorithm_id, parameters)

    # ------------------------------------------------------------------
    # Combined API + mouse methods
    # ------------------------------------------------------------------

    def load_layer_and_point(self, path: str, name: str) -> Any:
        """
        Load a layer via PyQGIS, then hover the mouse over the Layers panel.

        Parameters
        ----------
        path:
            Path/URI to the vector data source.
        name:
            Display name for the layer.

        Returns
        -------
        QgsVectorLayer
        """
        layer = self._bridge.load_vector_layer(path, name)
        self._automator.hover_region("layers_panel")
        logger.info("[Hybrid] Loaded layer '%s' and pointed at layers panel", name)
        return layer

    def zoom_to_layer_and_point(self, layer: Any, hover_duration: float = 1.5) -> None:
        """
        Zoom to *layer* via PyQGIS, then move mouse to the canvas centre.

        Parameters
        ----------
        layer:
            QgsVectorLayer or QgsMapLayer.
        hover_duration:
            How long (seconds) to dwell at the canvas centre.
        """
        self._bridge.zoom_to_layer(layer)
        if self._canvas_region:
            cx = self._canvas_region["x"] + self._canvas_region["width"] // 2
            cy = self._canvas_region["y"] + self._canvas_region["height"] // 2
            self._automator.move_mouse_to(cx, cy)
            self._automator.wait(hover_duration)
            logger.info("[Hybrid] Zoomed to layer and pointed canvas centre (%d, %d)", cx, cy)
        else:
            logger.warning("canvas_region not configured — skipping mouse move")

    def select_and_highlight(
        self,
        layer: Any,
        expression: str,
        hover_duration: float = 1.5,
    ) -> int:
        """
        Select features via PyQGIS, then highlight the canvas with the mouse.

        Parameters
        ----------
        layer:
            QgsVectorLayer.
        expression:
            QGIS expression string.
        hover_duration:
            Seconds to dwell after selection.

        Returns
        -------
        int
            Number of selected features.
        """
        count = self._bridge.select_features(layer, expression)
        if count > 0 and self._canvas_region:
            self._automator.highlight_area(self._canvas_region, duration=hover_duration)
            logger.info("[Hybrid] Selected %d features and highlighted canvas", count)
        return count

    # ------------------------------------------------------------------
    # Geo → screen coordinate conversion
    # ------------------------------------------------------------------

    def point_at_map_coordinate(
        self,
        geo_x: float,
        geo_y: float,
        duration: float | None = None,
        hover: float = 1.0,
    ) -> tuple[int, int] | None:
        """
        Move the mouse to the screen position corresponding to a geographic
        coordinate.

        Requires ``config['qgis']['canvas_region']`` to be set and a live
        ``iface.mapCanvas()`` to read the current extent.

        Parameters
        ----------
        geo_x:
            X coordinate in the project CRS (longitude or easting).
        geo_y:
            Y coordinate in the project CRS (latitude or northing).
        duration:
            Mouse move duration in seconds.  Uses AppAutomator default if None.
        hover:
            Seconds to dwell after reaching the position.

        Returns
        -------
        tuple[int, int] | None
            ``(screen_x, screen_y)`` or None if conversion was not possible.
        """
        result = self._geo_to_screen(geo_x, geo_y)
        if result is None:
            return None
        sx, sy = result
        self._automator.move_mouse_to(sx, sy, duration=duration)
        if hover > 0:
            self._automator.wait(hover)
        logger.info(
            "[Hybrid] Pointed at geo (%.4f, %.4f) → screen (%d, %d)",
            geo_x, geo_y, sx, sy,
        )
        return sx, sy

    def point_at_map_coordinate_list(
        self,
        coordinates: list[tuple[float, float]],
        dwell: float = 0.8,
        duration: float | None = None,
    ) -> None:
        """
        Move the mouse through a sequence of geographic coordinates.

        Useful for tracing a route or highlighting multiple points on the map
        in sequence for a tutorial.

        Parameters
        ----------
        coordinates:
            List of ``(geo_x, geo_y)`` tuples in the project CRS.
        dwell:
            Seconds to pause at each point.
        duration:
            Mouse move duration between points.
        """
        for geo_x, geo_y in coordinates:
            self.point_at_map_coordinate(geo_x, geo_y, duration=duration, hover=dwell)

    # ------------------------------------------------------------------
    # Low-level passthrough to AppAutomator
    # ------------------------------------------------------------------

    def move_mouse_to(self, x: int, y: int, duration: float | None = None) -> None:
        """Move mouse to absolute screen coordinates."""
        self._automator.move_mouse_to(x, y, duration=duration)

    def click_at(self, region_name: str, offset_x: int = 0, offset_y: int = 0) -> None:
        """Click a calibrated region."""
        self._automator.click_at(region_name, offset_x=offset_x, offset_y=offset_y)

    def click_at_xy(self, x: int, y: int) -> None:
        """Click at absolute screen coordinates."""
        self._automator.click_at_xy(x, y)

    def hover_region(self, region_name: str, duration: float = 1.5) -> None:
        """Hover the mouse over a calibrated region."""
        self._automator.hover_region(region_name, duration=duration)

    def highlight_area(self, region_name: str, duration: float = 2.0) -> None:
        """Circle the mouse around a calibrated region to highlight it."""
        self._automator.highlight_area(region_name, duration=duration)

    def wait(self, seconds: float) -> None:
        """Pause execution."""
        self._automator.wait(seconds)

    def screenshot(self, filepath: str) -> str:
        """Capture a full-screen screenshot."""
        return self._automator.screenshot(filepath)

    @property
    def bridge(self) -> Any:
        """Direct access to the underlying :class:`QGISBridge`."""
        return self._bridge

    @property
    def automator(self) -> Any:
        """Direct access to the underlying :class:`AppAutomator`."""
        return self._automator

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _geo_to_screen(
        self, geo_x: float, geo_y: float
    ) -> tuple[int, int] | None:
        """
        Convert a geographic point to absolute screen pixel coordinates.

        Uses the current ``iface.mapCanvas().extent()`` and the configured
        ``canvas_region`` to perform a bi-linear interpolation.

        Returns None when canvas_region is not configured or iface is
        unavailable.
        """
        if self._canvas_region is None:
            logger.warning(
                "geo_to_screen: canvas_region not set in config['qgis']['canvas_region']"
            )
            return None

        try:
            from qgis.utils import iface  # type: ignore
        except ImportError:
            logger.warning("geo_to_screen: iface not available — cannot convert coordinates")
            return None

        canvas = iface.mapCanvas()
        extent = canvas.extent()

        x_min = extent.xMinimum()
        x_max = extent.xMaximum()
        y_min = extent.yMinimum()
        y_max = extent.yMaximum()

        if x_max == x_min or y_max == y_min:
            logger.warning("geo_to_screen: degenerate canvas extent")
            return None

        cr = self._canvas_region
        # Bi-linear: geo → normalised [0,1] → screen pixel
        norm_x = (geo_x - x_min) / (x_max - x_min)
        # Y axis is flipped: geo_y increases upward, screen y increases downward
        norm_y = 1.0 - (geo_y - y_min) / (y_max - y_min)

        # Clamp to canvas boundaries
        norm_x = max(0.0, min(1.0, norm_x))
        norm_y = max(0.0, min(1.0, norm_y))

        screen_x = int(cr["x"] + norm_x * cr["width"])
        screen_y = int(cr["y"] + norm_y * cr["height"])

        return screen_x, screen_y
