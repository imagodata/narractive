"""
QGISBridge — Contrôle natif QGIS via API PyQGIS
================================================
Wrapper des opérations PyQGIS courantes. Utilisé par PyQGISController.
PyQGIS est importé lazily (try/except) pour ne pas bloquer si non disponible.

Usage::

    from video_automation.core.qgis_bridge import QGISBridge

    bridge = QGISBridge()
    bridge.load_vector_layer("data/regions.gpkg")
    bridge.select_features("regions", '"population" > 100000')
    result = bridge.run_algorithm("native:buffer", {"INPUT": layer, "DISTANCE": 1000})
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class QGISBridge:
    """
    Wraps common PyQGIS operations. Requires a running QgsApplication instance.

    All methods raise ``ImportError`` if PyQGIS (``qgis.core``) is not installed.
    """

    def __init__(self) -> None:
        self._check_pyqgis()

    def _check_pyqgis(self) -> None:
        """Raise ImportError if PyQGIS is not available."""
        try:
            import qgis.core  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "PyQGIS is not available. Install QGIS with Python bindings."
            ) from exc

    # ── Layer management ────────────────────────────────────────────────────

    def load_vector_layer(self, path: str | Path, layer_name: str | None = None) -> Any:
        """Load a vector layer into the current QGIS project."""
        from qgis.core import QgsProject, QgsVectorLayer  # type: ignore

        path = str(path)
        name = layer_name or Path(path).stem
        layer = QgsVectorLayer(path, name, "ogr")
        if not layer.isValid():
            raise ValueError(f"Failed to load vector layer: {path}")
        QgsProject.instance().addMapLayer(layer)
        logger.info("Loaded vector layer: %s", name)
        return layer

    def load_raster_layer(self, path: str | Path, layer_name: str | None = None) -> Any:
        """Load a raster layer into the current QGIS project."""
        from qgis.core import QgsProject, QgsRasterLayer  # type: ignore

        path = str(path)
        name = layer_name or Path(path).stem
        layer = QgsRasterLayer(path, name)
        if not layer.isValid():
            raise ValueError(f"Failed to load raster layer: {path}")
        QgsProject.instance().addMapLayer(layer)
        logger.info("Loaded raster layer: %s", name)
        return layer

    def remove_layer(self, layer_name: str) -> None:
        """Remove all layers with the given name from the current project."""
        from qgis.core import QgsProject  # type: ignore

        project = QgsProject.instance()
        for layer in project.mapLayersByName(layer_name):
            project.removeMapLayer(layer.id())
        logger.info("Removed layer(s): %s", layer_name)

    # ── View / extent ───────────────────────────────────────────────────────

    def set_extent(
        self,
        xmin: float,
        ymin: float,
        xmax: float,
        ymax: float,
        crs_epsg: int | None = None,
    ) -> None:
        """Set the map canvas extent."""
        from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle  # type: ignore

        try:
            from qgis.utils import iface  # type: ignore

            canvas = iface.mapCanvas()
            extent = QgsRectangle(xmin, ymin, xmax, ymax)
            if crs_epsg:
                crs = QgsCoordinateReferenceSystem(f"EPSG:{crs_epsg}")
                canvas.setDestinationCrs(crs)
            canvas.setExtent(extent)
            canvas.refresh()
            logger.info("Extent set to %s", extent.toString())
        except Exception:
            logger.warning("iface not available — cannot set canvas extent")

    def zoom_to_layer(self, layer_name: str) -> None:
        """Zoom the canvas to a layer's extent."""
        from qgis.core import QgsProject  # type: ignore

        layers = QgsProject.instance().mapLayersByName(layer_name)
        if not layers:
            raise ValueError(f"Layer not found: {layer_name}")
        try:
            from qgis.utils import iface  # type: ignore

            iface.setActiveLayer(layers[0])
            iface.zoomToActiveLayer()
        except Exception:
            logger.warning("iface not available — cannot zoom to layer")

    # ── Selection ───────────────────────────────────────────────────────────

    def select_features(self, layer_name: str, expression: str) -> int:
        """Select features in a layer using a QGIS expression. Returns selected count."""
        from qgis.core import QgsExpression, QgsFeatureRequest, QgsProject  # type: ignore

        layers = QgsProject.instance().mapLayersByName(layer_name)
        if not layers:
            raise ValueError(f"Layer not found: {layer_name}")
        layer = layers[0]
        expr = QgsExpression(expression)
        request = QgsFeatureRequest(expr)
        ids = [f.id() for f in layer.getFeatures(request)]
        layer.selectByIds(ids)
        logger.info("Selected %d features in '%s'", len(ids), layer_name)
        return len(ids)

    def clear_selection(self, layer_name: str | None = None) -> None:
        """Clear selection on a specific layer or all layers."""
        from qgis.core import QgsProject  # type: ignore

        project = QgsProject.instance()
        if layer_name:
            for layer in project.mapLayersByName(layer_name):
                layer.removeSelection()
        else:
            for layer in project.mapLayers().values():
                if hasattr(layer, "removeSelection"):
                    layer.removeSelection()

    # ── Processing ──────────────────────────────────────────────────────────

    def run_algorithm(self, algorithm_id: str, params: dict) -> dict:
        """Run a QGIS processing algorithm."""
        try:
            import processing  # type: ignore
        except ImportError as exc:
            raise ImportError("QGIS processing module not available") from exc
        result = processing.run(algorithm_id, params)
        logger.info("Algorithm '%s' completed", algorithm_id)
        return result

    # ── Project info ────────────────────────────────────────────────────────

    def get_project_layers(self) -> list[dict]:
        """Return info about all layers in the current project."""
        from qgis.core import QgsProject  # type: ignore

        layers = []
        for layer in QgsProject.instance().mapLayers().values():
            layers.append(
                {
                    "id": layer.id(),
                    "name": layer.name(),
                    "type": (
                        layer.type().name
                        if hasattr(layer.type(), "name")
                        else str(layer.type())
                    ),
                    "visible": True,
                }
            )
        return layers

    def open_project(self, project_path: str | Path) -> None:
        """Open a QGIS project file."""
        from qgis.core import QgsProject  # type: ignore

        ok = QgsProject.instance().read(str(project_path))
        if not ok:
            raise ValueError(f"Failed to open QGIS project: {project_path}")
        logger.info("Opened project: %s", project_path)

    def save_project(self, project_path: str | Path | None = None) -> None:
        """Save the current QGIS project."""
        from qgis.core import QgsProject  # type: ignore

        if project_path:
            QgsProject.instance().setFileName(str(project_path))
        ok = QgsProject.instance().write()
        if not ok:
            raise ValueError("Failed to save QGIS project")
        logger.info("Project saved")
