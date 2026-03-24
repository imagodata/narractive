"""
QGIS Headless Renderer — Server-side / CI map rendering without a display
==========================================================================
Renders QGIS project maps to PNG files without opening a GUI.

Usage::

    from video_automation.core.qgis_headless import HeadlessRenderer

    renderer = HeadlessRenderer()
    renderer.render("my_project.qgz", "output.png", size=(1920, 1080))

Environment variables
---------------------
QGIS_PREFIX_PATH
    Override the QGIS installation prefix (e.g. ``/usr`` on Ubuntu).
    Defaults to the value detected at runtime.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default QGIS prefix path — can be overridden via env var
_DEFAULT_PREFIX = os.environ.get("QGIS_PREFIX_PATH", "/usr")


def _bootstrap_qgis(prefix_path: str = _DEFAULT_PREFIX) -> Any:
    """
    Initialise a headless :class:`QgsApplication` instance.

    Parameters
    ----------
    prefix_path:
        Path to the QGIS installation prefix (parent of ``share/qgis``).
        Defaults to ``QGIS_PREFIX_PATH`` env var or ``/usr``.

    Returns
    -------
    QgsApplication
        The initialised application object (caller must keep a reference).

    Raises
    ------
    ImportError
        If PyQGIS is not available.
    """
    try:
        from qgis.core import QgsApplication  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "PyQGIS (qgis.core) is not available in this environment. "
            "Install PyQGIS or set QGIS_PREFIX_PATH correctly."
        ) from exc

    # gui_flag=False for headless operation
    qgs = QgsApplication([], False)
    qgs.setPrefixPath(prefix_path, True)
    qgs.initQgis()
    logger.debug("QgsApplication initialised (prefix=%s)", prefix_path)
    return qgs


class HeadlessRenderer:
    """
    Render QGIS projects to PNG images without a display.

    Parameters
    ----------
    prefix_path:
        QGIS installation prefix. Falls back to ``QGIS_PREFIX_PATH`` env
        variable or ``/usr`` if not provided.
    """

    def __init__(self, prefix_path: str | None = None) -> None:
        self._prefix_path = prefix_path or _DEFAULT_PREFIX
        # Validate that PyQGIS is importable at construction time
        try:
            import qgis.core  # type: ignore  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "PyQGIS (qgis.core) is not available in this environment. "
                "Install PyQGIS or set QGIS_PREFIX_PATH correctly."
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        project_path: str,
        output_png: str,
        extent: tuple[float, float, float, float] | None = None,
        size: tuple[int, int] = (1920, 1080),
        dpi: int = 96,
    ) -> Path:
        """
        Render the default map view of a QGIS project to a PNG file.

        Parameters
        ----------
        project_path:
            Path to a ``.qgz`` or ``.qgs`` project file.
        output_png:
            Destination PNG file path.
        extent:
            Optional bounding box ``(xmin, ymin, xmax, ymax)`` in project CRS.
            If *None*, uses the full layer extent.
        size:
            Output image dimensions ``(width, height)`` in pixels.
        dpi:
            Resolution in dots per inch.

        Returns
        -------
        Path
            The path to the written PNG file.
        """
        from qgis.core import (  # type: ignore
            QgsMapRendererParallelJob,
            QgsMapSettings,
            QgsProject,
            QgsRectangle,
        )
        from qgis.PyQt.QtCore import QSize  # type: ignore
        from qgis.PyQt.QtGui import QColor  # type: ignore

        qgs = _bootstrap_qgis(self._prefix_path)
        try:
            project = QgsProject.instance()
            project.read(project_path)

            layers = list(project.mapLayers().values())
            if not layers:
                raise ValueError(f"Project has no layers: {project_path}")

            settings = QgsMapSettings()
            settings.setLayers(layers)
            settings.setOutputSize(QSize(*size))
            settings.setOutputDpi(dpi)
            settings.setBackgroundColor(QColor("white"))

            if extent:
                xmin, ymin, xmax, ymax = extent
                settings.setExtent(QgsRectangle(xmin, ymin, xmax, ymax))
            else:
                combined = layers[0].extent()
                for lyr in layers[1:]:
                    combined.combineExtentWith(lyr.extent())
                settings.setExtent(combined)

            render_job = QgsMapRendererParallelJob(settings)
            render_job.start()
            render_job.waitForFinished()

            img = render_job.renderedImage()
            out_path = Path(output_png)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(str(out_path))
            logger.info("Rendered map to %s", out_path)
            return out_path
        finally:
            qgs.exitQgis()

    def render_layout(
        self,
        project_path: str,
        layout_name: str,
        output_png: str,
        dpi: int = 150,
    ) -> Path:
        """
        Export a named print layout from a QGIS project to PNG.

        Parameters
        ----------
        project_path:
            Path to the ``.qgz`` / ``.qgs`` project file.
        layout_name:
            The name of the print layout as defined in QGIS.
        output_png:
            Destination PNG file path.
        dpi:
            Resolution in dots per inch for the export.

        Returns
        -------
        Path
            The path to the written PNG file.

        Raises
        ------
        KeyError
            If no layout with *layout_name* exists in the project.
        """
        from qgis.core import (  # type: ignore
            QgsLayoutExporter,
            QgsProject,
        )

        qgs = _bootstrap_qgis(self._prefix_path)
        try:
            project = QgsProject.instance()
            project.read(project_path)

            layout_manager = project.layoutManager()
            layout = layout_manager.layoutByName(layout_name)
            if layout is None:
                available = [l.name() for l in layout_manager.layouts()]
                raise KeyError(
                    f"Layout '{layout_name}' not found in project. "
                    f"Available: {available}"
                )

            out_path = Path(output_png)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            exporter = QgsLayoutExporter(layout)
            settings = QgsLayoutExporter.ImageExportSettings()
            settings.dpi = dpi
            result = exporter.exportToImage(str(out_path), settings)

            if result != QgsLayoutExporter.Success:
                raise RuntimeError(
                    f"Layout export failed (code {result}) for '{layout_name}'"
                )

            logger.info("Exported layout '%s' to %s", layout_name, out_path)
            return out_path
        finally:
            qgs.exitQgis()
