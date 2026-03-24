"""
QGIS Bridge — Thin wrapper around common PyQGIS operations
===========================================================
All methods perform a lazy import of ``qgis.core`` and raise
:class:`ImportError` cleanly when PyQGIS is not available in the
current environment.

Usage::

    from narractive.core.qgis_bridge import QGISBridge

    bridge = QGISBridge()
    layer = bridge.load_vector_layer("/path/to/file.shp", "my_layer")
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _require_qgis() -> Any:
    """Import qgis.core or raise a clear ImportError."""
    try:
        import qgis.core as qgis_core  # type: ignore
        return qgis_core
    except ImportError as exc:
        raise ImportError(
            "PyQGIS (qgis.core) is not available in this environment. "
            "Run inside a QGIS Python console or install PyQGIS."
        ) from exc


class QGISBridge:
    """
    High-level facade for the most common PyQGIS operations.

    All public methods import ``qgis.core`` lazily so that the class can
    be imported safely in environments without PyQGIS — the ImportError is
    only raised when a method is actually called.
    """

    # ------------------------------------------------------------------
    # Layer management
    # ------------------------------------------------------------------

    def load_vector_layer(self, path: str, name: str) -> Any:
        """
        Load a vector layer from *path* and add it to the current project.

        Parameters
        ----------
        path:
            Filesystem path or URI to the vector data source.
        name:
            Display name for the layer.

        Returns
        -------
        QgsVectorLayer
        """
        qgis_core = _require_qgis()
        layer = qgis_core.QgsVectorLayer(path, name, "ogr")
        if not layer.isValid():
            raise ValueError(f"Failed to load vector layer: {path}")
        qgis_core.QgsProject.instance().addMapLayer(layer)
        logger.debug("Loaded vector layer '%s' from %s", name, path)
        return layer

    def load_raster_layer(self, path: str, name: str) -> Any:
        """
        Load a raster layer from *path* and add it to the current project.

        Parameters
        ----------
        path:
            Filesystem path or URI to the raster data source.
        name:
            Display name for the layer.

        Returns
        -------
        QgsRasterLayer
        """
        qgis_core = _require_qgis()
        layer = qgis_core.QgsRasterLayer(path, name)
        if not layer.isValid():
            raise ValueError(f"Failed to load raster layer: {path}")
        qgis_core.QgsProject.instance().addMapLayer(layer)
        logger.debug("Loaded raster layer '%s' from %s", name, path)
        return layer

    def remove_layer(self, layer_id: str) -> None:
        """
        Remove a layer by its ID from the current project.

        Parameters
        ----------
        layer_id:
            The unique layer ID string.
        """
        qgis_core = _require_qgis()
        qgis_core.QgsProject.instance().removeMapLayer(layer_id)
        logger.debug("Removed layer %s", layer_id)

    # ------------------------------------------------------------------
    # View / extent
    # ------------------------------------------------------------------

    def set_extent(self, xmin: float, ymin: float, xmax: float, ymax: float) -> None:
        """
        Set the map canvas extent to the given bounding box.

        Parameters
        ----------
        xmin, ymin, xmax, ymax:
            Bounding box coordinates in the project CRS.
        """
        qgis_core = _require_qgis()
        rect = qgis_core.QgsRectangle(xmin, ymin, xmax, ymax)
        iface = _get_iface()
        if iface is not None:
            iface.mapCanvas().setExtent(rect)
            iface.mapCanvas().refresh()
        else:
            logger.warning("set_extent: iface not available (headless mode?)")

    def zoom_to_layer(self, layer: Any) -> None:
        """
        Zoom the map canvas to the extent of *layer*.

        Parameters
        ----------
        layer:
            A QgsMapLayer instance.
        """
        _require_qgis()
        iface = _get_iface()
        if iface is not None:
            iface.mapCanvas().setExtent(layer.extent())
            iface.mapCanvas().refresh()
        else:
            logger.warning("zoom_to_layer: iface not available (headless mode?)")

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_features(self, layer: Any, expression: str) -> int:
        """
        Select features in *layer* matching *expression*.

        Parameters
        ----------
        layer:
            A QgsVectorLayer.
        expression:
            A QGIS expression string, e.g. ``"population" > 10000``.

        Returns
        -------
        int
            Number of selected features.
        """
        _require_qgis()
        layer.selectByExpression(expression)
        count = layer.selectedFeatureCount()
        logger.debug("Selected %d features with expression: %s", count, expression)
        return count

    def clear_selection(self, layer: Any) -> None:
        """
        Clear the current selection in *layer*.

        Parameters
        ----------
        layer:
            A QgsVectorLayer.
        """
        _require_qgis()
        layer.removeSelection()
        logger.debug("Cleared selection on layer %s", layer.name())

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def run_algorithm(self, algorithm_id: str, parameters: dict) -> dict:
        """
        Run a QGIS Processing algorithm.

        Parameters
        ----------
        algorithm_id:
            The full algorithm ID, e.g. ``"native:buffer"``.
        parameters:
            Dictionary of algorithm parameters.

        Returns
        -------
        dict
            The algorithm results dictionary.
        """
        _require_qgis()
        try:
            import processing  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "QGIS Processing framework is not available. "
                "Make sure processing is initialised."
            ) from exc
        results = processing.run(algorithm_id, parameters)
        logger.debug("Algorithm '%s' completed", algorithm_id)
        return results

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------

    def get_project_layers(self) -> dict[str, Any]:
        """
        Return a mapping of layer ID -> QgsMapLayer for all project layers.
        """
        qgis_core = _require_qgis()
        return dict(qgis_core.QgsProject.instance().mapLayers())

    def open_project(self, path: str) -> bool:
        """
        Open a QGIS project file.

        Parameters
        ----------
        path:
            Filesystem path to a ``.qgz`` or ``.qgs`` file.

        Returns
        -------
        bool
            True on success.
        """
        qgis_core = _require_qgis()
        ok = qgis_core.QgsProject.instance().read(path)
        if not ok:
            raise OSError(f"Failed to open QGIS project: {path}")
        logger.debug("Opened project: %s", path)
        return ok

    def save_project(self, path: str | None = None) -> bool:
        """
        Save the current QGIS project.

        Parameters
        ----------
        path:
            Optional path to save-as. If None, saves in place.

        Returns
        -------
        bool
            True on success.
        """
        qgis_core = _require_qgis()
        project = qgis_core.QgsProject.instance()
        if path:
            project.setFileName(path)
        ok = project.write()
        if not ok:
            raise OSError("Failed to save QGIS project.")
        logger.debug("Project saved%s", f" to {path}" if path else "")
        return ok


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _get_iface() -> Any:
    """Return the QGIS iface object if available, else None."""
    try:
        from qgis.utils import iface  # type: ignore
        return iface
    except ImportError:
        return None
