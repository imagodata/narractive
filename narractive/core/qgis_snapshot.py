"""
QGIS Snapshot — Capture and restore map state as JSON
======================================================
Serialises the current QGIS map state (project path, CRS, extent, layer
visibility, selections, filters) to a JSON file, and can restore that state
later.

Snapshots do **not** require PyQGIS for save/load/list operations; only
:meth:`QGISSnapshot.capture` and :meth:`QGISSnapshot.restore` need a live
QGIS session.

Usage::

    # Inside a QGIS Python console or PyQGIS script:
    from narractive.core.qgis_snapshot import QGISSnapshot

    snap = QGISSnapshot.capture()
    snap.save("my_snapshot")

    # Later:
    snap = QGISSnapshot.load("diagrams/snapshots/my_snapshot.json")
    snap.restore()

Snapshots are stored under ``diagrams/snapshots/`` by default.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SNAPSHOT_DIR = Path("diagrams/snapshots")


class QGISSnapshot:
    """
    Immutable representation of a QGIS map state.

    Attributes
    ----------
    project_path : str | None
        Absolute path to the ``.qgz``/``.qgs`` project file.
    crs_epsg : int | None
        EPSG code of the project CRS (e.g. 4326).
    extent : dict | None
        Bounding box with keys ``xmin``, ``ymin``, ``xmax``, ``ymax``.
    layers : list[dict]
        Per-layer state records (id, name, visible, type, selected_ids, filter).
    created_at : str
        ISO-8601 timestamp of when the snapshot was taken.
    """

    def __init__(
        self,
        *,
        project_path: str | None = None,
        crs_epsg: int | None = None,
        extent: dict[str, float] | None = None,
        layers: list[dict[str, Any]] | None = None,
        created_at: str | None = None,
    ) -> None:
        self.project_path = project_path
        self.crs_epsg = crs_epsg
        self.extent = extent or {}
        self.layers: list[dict[str, Any]] = layers or []
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    @classmethod
    def capture(cls) -> "QGISSnapshot":
        """
        Capture the current QGIS project state.

        Returns
        -------
        QGISSnapshot
            A snapshot of the live session.

        Raises
        ------
        ImportError
            If PyQGIS is not available.
        """
        try:
            from qgis.core import QgsProject  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "PyQGIS (qgis.core) is not available. "
                "Run capture() inside a QGIS Python session."
            ) from exc

        project = QgsProject.instance()

        # Project path
        project_path: str | None = project.fileName() or None

        # CRS
        crs = project.crs()
        crs_epsg: int | None = crs.postgisSrid() if crs.isValid() else None

        # Extent — from map canvas if available
        extent_dict: dict[str, float] = {}
        try:
            from qgis.utils import iface  # type: ignore
            if iface is not None:
                ext = iface.mapCanvas().extent()
                extent_dict = {
                    "xmin": ext.xMinimum(),
                    "ymin": ext.yMinimum(),
                    "xmax": ext.xMaximum(),
                    "ymax": ext.yMaximum(),
                }
        except Exception:
            pass

        # Layers
        layers_data: list[dict[str, Any]] = []
        for layer_id, layer in project.mapLayers().items():
            layer_type = layer.type()
            # QgsMapLayerType: 0=VectorLayer, 1=RasterLayer
            type_name = {0: "vector", 1: "raster"}.get(int(layer_type), "unknown")

            selected_ids: list[int] = []
            filter_expr: str = ""
            if type_name == "vector":
                try:
                    selected_ids = [f.id() for f in layer.selectedFeatures()]
                    filter_expr = layer.subsetString() or ""
                except Exception:
                    pass

            node = project.layerTreeRoot().findLayer(layer_id)
            visible = node.isVisible() if node is not None else True

            layers_data.append(
                {
                    "id": layer_id,
                    "name": layer.name(),
                    "visible": visible,
                    "type": type_name,
                    "selected_ids": selected_ids,
                    "filter": filter_expr,
                }
            )

        snap = cls(
            project_path=project_path,
            crs_epsg=crs_epsg,
            extent=extent_dict,
            layers=layers_data,
        )
        logger.debug(
            "Captured snapshot: %d layers, extent=%s", len(layers_data), extent_dict
        )
        return snap

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def restore(self) -> None:
        """
        Restore the map state stored in this snapshot to the live QGIS session.

        Raises
        ------
        ImportError
            If PyQGIS is not available.
        """
        try:
            from qgis.core import QgsProject, QgsRectangle  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "PyQGIS (qgis.core) is not available. "
                "Run restore() inside a QGIS Python session."
            ) from exc

        project = QgsProject.instance()

        # Open project if path differs
        if self.project_path and project.fileName() != self.project_path:
            project.read(self.project_path)
            logger.debug("Opened project: %s", self.project_path)

        # Restore layer states
        for layer_state in self.layers:
            layer_id = layer_state.get("id", "")
            layer = project.mapLayer(layer_id)
            if layer is None:
                logger.warning("Layer %s not found, skipping restore", layer_id)
                continue

            # Visibility
            node = project.layerTreeRoot().findLayer(layer_id)
            if node is not None:
                node.setItemVisibilityChecked(layer_state.get("visible", True))

            # Filter expression (vector only)
            if layer_state.get("type") == "vector":
                try:
                    layer.setSubsetString(layer_state.get("filter", ""))
                    # Re-select features
                    selected_ids = layer_state.get("selected_ids", [])
                    if selected_ids:
                        layer.selectByIds(selected_ids)
                    else:
                        layer.removeSelection()
                except Exception as exc:
                    logger.warning("Could not restore vector state for %s: %s", layer_id, exc)

        # Restore extent
        if self.extent:
            try:
                from qgis.utils import iface  # type: ignore
                rect = QgsRectangle(
                    self.extent["xmin"],
                    self.extent["ymin"],
                    self.extent["xmax"],
                    self.extent["ymax"],
                )
                if iface is not None:
                    iface.mapCanvas().setExtent(rect)
                    iface.mapCanvas().refresh()
            except Exception as exc:
                logger.warning("Could not restore extent: %s", exc)

        logger.debug("Snapshot restored (%d layers)", len(self.layers))

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return {
            "project_path": self.project_path,
            "crs_epsg": self.crs_epsg,
            "extent": self.extent,
            "layers": self.layers,
            "created_at": self.created_at,
        }

    def save(self, name_or_path: str) -> Path:
        """
        Save this snapshot to a JSON file.

        Parameters
        ----------
        name_or_path:
            Either a bare name (e.g. ``"before_filter"``), which will be saved
            as ``diagrams/snapshots/<name>.json``, or a full file path.

        Returns
        -------
        Path
            The path where the file was written.
        """
        p = Path(name_or_path)
        if p.suffix != ".json":
            p = self.snapshot_dir() / f"{name_or_path}.json"

        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.debug("Snapshot saved to %s", p)
        return p

    @classmethod
    def load(cls, path: str | Path) -> "QGISSnapshot":
        """
        Load a snapshot from a JSON file.

        Parameters
        ----------
        path:
            Path to the ``.json`` snapshot file.

        Returns
        -------
        QGISSnapshot
        """
        p = Path(path)
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        snap = cls(
            project_path=data.get("project_path"),
            crs_epsg=data.get("crs_epsg"),
            extent=data.get("extent"),
            layers=data.get("layers", []),
            created_at=data.get("created_at"),
        )
        logger.debug("Snapshot loaded from %s", p)
        return snap

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def snapshot_dir(base: str | Path | None = None) -> Path:
        """
        Return the snapshots directory.

        Parameters
        ----------
        base:
            Optional base directory. If not provided, defaults to
            ``diagrams/snapshots`` relative to the current working directory.
        """
        if base is not None:
            return Path(base) / "snapshots"
        return _SNAPSHOT_DIR

    @classmethod
    def list_snapshots(cls, directory: str | Path | None = None) -> list[Path]:
        """
        List all ``.json`` snapshot files in *directory*.

        Parameters
        ----------
        directory:
            Directory to scan. Defaults to :meth:`snapshot_dir`.

        Returns
        -------
        list[Path]
            Sorted list of snapshot file paths.
        """
        snap_dir = Path(directory) if directory is not None else cls.snapshot_dir()
        if not snap_dir.exists():
            return []
        return sorted(snap_dir.glob("*.json"))

    def __repr__(self) -> str:
        return (
            f"QGISSnapshot(project={self.project_path!r}, "
            f"layers={len(self.layers)}, created_at={self.created_at!r})"
        )
