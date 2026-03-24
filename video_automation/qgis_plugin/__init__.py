"""
Narractive QGIS Plugin — __init__.py
=====================================
Entry point for the QGIS plugin loader.  QGIS calls :func:`classFactory`
with its ``iface`` object to obtain the plugin instance.
"""

from __future__ import annotations


def classFactory(iface):  # noqa: N802 — QGIS naming convention
    """
    QGIS plugin loader entry point.

    Parameters
    ----------
    iface : QgisInterface
        The QGIS interface object provided by the application.

    Returns
    -------
    NarractivePlugin
        Initialised plugin instance.
    """
    from .plugin_main import NarractivePlugin  # type: ignore

    return NarractivePlugin(iface)
