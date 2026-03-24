"""
QGIS Headless Renderer
=======================
Bootstraps QGIS without a display and renders map canvases to PNG images
via ``QgsMapRendererParallelJob``.

Requirements:
    - QGIS installed with Python bindings (``qgis.core``)
    - ``QGIS_PREFIX_PATH`` env variable pointing to QGIS installation, or
      pass ``prefix_path`` directly.
    - No display server required.

Usage::

    from video_automation.core.qgis_headless import HeadlessRenderer

    renderer = HeadlessRenderer()
    out = renderer.render(
        project_path="my_project.qgz",
        output_png="output/map.png",
        size=(1920, 1080),
    )
    print(f"Rendered: {out}")

    # Render a named print layout
    renderer.render_layout("my_project.qgz", "Main Map", "output/layout.png")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _bootstrap_qgis(prefix_path: str | None = None) -> None:
    """
    Initialize a headless QgsApplication if not already running.

    Parameters
    ----------
    prefix_path : str, optional
        Path to QGIS installation prefix (e.g. ``/usr`` or ``/usr/local``).
        Defaults to the ``QGIS_PREFIX_PATH`` environment variable, or ``/usr``.
    """
    try:
        from qgis.core import QgsApplication  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "PyQGIS not available. Set QGIS_PREFIX_PATH and ensure QGIS Python "
            "bindings are installed."
        ) from exc

    if QgsApplication.instance() is not None:
        return  # Already initialized

    qgis_prefix = prefix_path or os.environ.get("QGIS_PREFIX_PATH", "/usr")
    os.environ.setdefault("QGIS_PREFIX_PATH", qgis_prefix)

    app = QgsApplication([], False)  # [] = no argv, False = no GUI
    app.setPrefixPath(qgis_prefix, True)
    app.initQgis()
    logger.info("QGIS initialized (headless) with prefix: %s", qgis_prefix)


class HeadlessRenderer:
    """
    Renders QGIS project maps to PNG without opening the QGIS GUI.

    Parameters
    ----------
    prefix_path : str, optional
        Path to QGIS installation (e.g. ``/usr`` or ``/usr/local``).
        Defaults to ``QGIS_PREFIX_PATH`` env variable or ``/usr``.
    """

    def __init__(self, prefix_path: str | None = None) -> None:
        self.prefix_path = prefix_path
        _bootstrap_qgis(prefix_path)

    def render(
        self,
        project_path: str | Path,
        output_png: str | Path,
        extent: tuple[float, float, float, float] | None = None,
        size: tuple[int, int] = (1920, 1080),
        dpi: int = 96,
    ) -> Path:
        """
        Render a QGIS project map view to a PNG file.

        Parameters
        ----------
        project_path : str | Path
            Path to ``.qgz`` or ``.qgs`` project file.
        output_png : str | Path
            Output PNG file path.
        extent : tuple (xmin, ymin, xmax, ymax), optional
            Map extent in project CRS. Defaults to the full extent of all layers.
        size : tuple (width, height)
            Output image size in pixels. Default: ``(1920, 1080)``.
        dpi : int
            Image DPI. Default: ``96``.

        Returns
        -------
        Path
            Path to the rendered PNG file.
        """
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

        project_path = Path(project_path)
        output_png = Path(output_png)
        output_png.parent.mkdir(parents=True, exist_ok=True)

        project = QgsProject.instance()
        ok = project.read(str(project_path))
        if not ok:
            raise ValueError(f"Failed to load project: {project_path}")

        logger.info("Rendering project: %s → %s", project_path.name, output_png.name)

        settings = QgsMapSettings()
        settings.setLayers(list(project.mapLayers().values()))
        settings.setOutputSize(QSize(*size))
        settings.setOutputDpi(dpi)

        if extent:
            settings.setExtent(QgsRectangle(*extent))
        else:
            full_extent = QgsRectangle()
            for layer in project.mapLayers().values():
                full_extent.combineExtentWith(layer.extent())
            settings.setExtent(full_extent)

        job = QgsMapRendererParallelJob(settings)
        job.start()
        job.waitForFinished()

        image = job.renderedImage()
        ok = image.save(str(output_png), "PNG")
        if not ok:
            raise RuntimeError(f"Failed to save PNG: {output_png}")

        logger.info("Rendered map saved: %s (%dx%d)", output_png, *size)
        return output_png

    def render_layout(
        self,
        project_path: str | Path,
        layout_name: str,
        output_png: str | Path,
        dpi: int = 150,
    ) -> Path:
        """
        Render a named print layout from a QGIS project to PNG.

        Parameters
        ----------
        project_path : str | Path
            Path to QGIS project.
        layout_name : str
            Name of the print layout in the project.
        output_png : str | Path
            Output PNG file path.
        dpi : int
            Render DPI. Default: ``150``.

        Returns
        -------
        Path
            Path to the rendered PNG file.
        """
        from qgis.core import QgsLayoutExporter, QgsProject  # type: ignore

        project_path = Path(project_path)
        output_png = Path(output_png)
        output_png.parent.mkdir(parents=True, exist_ok=True)

        project = QgsProject.instance()
        project.read(str(project_path))

        layout_manager = project.layoutManager()
        layout = layout_manager.layoutByName(layout_name)
        if layout is None:
            raise ValueError(f"Layout '{layout_name}' not found in project")

        exporter = QgsLayoutExporter(layout)
        settings = QgsLayoutExporter.ImageExportSettings()
        settings.dpi = dpi

        result = exporter.exportToImage(str(output_png), settings)
        if result != QgsLayoutExporter.Success:
            raise RuntimeError(f"Layout export failed (code {result})")

        logger.info("Layout '%s' rendered to: %s", layout_name, output_png)
        return output_png
