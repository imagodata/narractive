"""
QGIS Snapshot API
==================
Capture and restore the complete runtime state of a QGIS project session:
visible layers, map extent, feature selections, and active filters.

The capture/restore methods require a running QGIS instance (``qgis.utils.iface``).
The save/load/list helpers work without PyQGIS.

Usage::

    from video_automation.core.qgis_snapshot import QGISSnapshot

    # Inside QGIS:
    snapshot = QGISSnapshot.capture()
    snapshot.save("diagrams/snapshots/scene_A.json")

    # Restore later:
    s = QGISSnapshot.load("diagrams/snapshots/scene_A.json")
    s.restore()

CLI::

    narractive snapshot capture <name>
    narractive snapshot restore <name>
    narractive snapshot list
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_SNAPSHOT_DIR = Path("diagrams/snapshots")


class QGISSnapshot:
    """
    Serializable snapshot of a QGIS project's runtime state.

    Attributes
    ----------
    data : dict
        Raw snapshot data (JSON-serializable).
    """

    def __init__(self, data: dict) -> None:
        self.data = data

    # ── Capture ────────────────────────────────────────────────────────────

    @classmethod
    def capture(cls) -> "QGISSnapshot":
        """
        Capture the current QGIS state from a running QGIS instance.

        Requires ``qgis.utils.iface`` to be available (i.e. must run inside QGIS
        or with a running ``QgsApplication``).

        Returns
        -------
        QGISSnapshot
        """
        try:
            from qgis.core import QgsProject  # type: ignore
            from qgis.utils import iface  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "PyQGIS / iface not available — QGISSnapshot.capture() must run "
                "inside a QGIS session."
            ) from exc

        project = QgsProject.instance()
        canvas = iface.mapCanvas()
        extent = canvas.extent()
        crs = canvas.mapSettings().destinationCrs()

        layers_state: list[dict[str, Any]] = []
        root = project.layerTreeRoot()
        for node in root.findLayers():
            layer = node.layer()
            if layer is None:
                continue
            state: dict[str, Any] = {
                "id": layer.id(),
                "name": layer.name(),
                "visible": node.isVisible(),
                "type": (
                    layer.type().name
                    if hasattr(layer.type(), "name")
                    else str(layer.type())
                ),
            }
            if hasattr(layer, "selectedFeatureIds"):
                state["selected_ids"] = list(layer.selectedFeatureIds())
            if hasattr(layer, "subsetString"):
                state["filter"] = layer.subsetString()
            layers_state.append(state)

        data: dict[str, Any] = {
            "project_path": project.fileName(),
            "crs_epsg": crs.authid(),
            "extent": {
                "xmin": extent.xMinimum(),
                "ymin": extent.yMinimum(),
                "xmax": extent.xMaximum(),
                "ymax": extent.yMaximum(),
            },
            "layers": layers_state,
        }

        logger.info("Snapshot captured: %d layers", len(layers_state))
        return cls(data)

    # ── Restore ────────────────────────────────────────────────────────────

    def restore(self) -> None:
        """
        Restore QGIS state from this snapshot.

        Requires a running QGIS instance.
        """
        try:
            from qgis.core import (  # type: ignore
                QgsCoordinateReferenceSystem,
                QgsProject,
                QgsRectangle,
            )
            from qgis.utils import iface  # type: ignore
        except ImportError as exc:
            raise ImportError("PyQGIS / iface not available") from exc

        project = QgsProject.instance()
        canvas = iface.mapCanvas()

        # Restore extent and CRS
        extent_data = self.data.get("extent", {})
        if extent_data:
            extent = QgsRectangle(
                extent_data["xmin"],
                extent_data["ymin"],
                extent_data["xmax"],
                extent_data["ymax"],
            )
            crs_id = self.data.get("crs_epsg", "")
            if crs_id:
                crs = QgsCoordinateReferenceSystem(crs_id)
                canvas.setDestinationCrs(crs)
            canvas.setExtent(extent)

        # Restore layer states
        root = project.layerTreeRoot()
        for layer_state in self.data.get("layers", []):
            layer_id = layer_state.get("id")
            layer = project.mapLayer(layer_id)
            if layer is None:
                logger.warning(
                    "Layer not found: %s (%s)", layer_state.get("name"), layer_id
                )
                continue

            # Visibility
            node = root.findLayer(layer_id)
            if node:
                node.setItemVisibilityChecked(layer_state.get("visible", True))

            # Selection
            if "selected_ids" in layer_state and hasattr(layer, "selectByIds"):
                layer.selectByIds(layer_state["selected_ids"])

            # Filter
            if "filter" in layer_state and hasattr(layer, "setSubsetString"):
                layer.setSubsetString(layer_state["filter"])

        canvas.refresh()
        logger.info(
            "Snapshot restored: %d layers", len(self.data.get("layers", []))
        )

    # ── Persistence ────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> Path:
        """
        Save this snapshot to a JSON file.

        Parameters
        ----------
        path : str | Path
            Destination file path (parent dirs are created if needed).

        Returns
        -------
        Path
            Absolute path to the saved file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Snapshot saved: %s", path)
        return path

    @classmethod
    def load(cls, path: str | Path) -> "QGISSnapshot":
        """
        Load a snapshot from a JSON file.

        Parameters
        ----------
        path : str | Path
            Path to the snapshot JSON file.
        """
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data)

    # ── Directory helpers ──────────────────────────────────────────────────

    @staticmethod
    def list_snapshots(
        directory: str | Path = _DEFAULT_SNAPSHOT_DIR,
    ) -> list[Path]:
        """Return all snapshot JSON files in *directory*, sorted by name."""
        directory = Path(directory)
        if not directory.exists():
            return []
        return sorted(directory.glob("*.json"))

    @staticmethod
    def snapshot_dir(base: str | Path = ".") -> Path:
        """Return the canonical snapshot directory relative to *base*."""
        return Path(base) / _DEFAULT_SNAPSHOT_DIR
