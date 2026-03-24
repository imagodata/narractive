"""QGIS Plugin entry point for Narractive."""


def classFactory(iface):  # noqa: N802
    """Required by QGIS plugin loader."""
    from .plugin_main import NarractivePlugin

    return NarractivePlugin(iface)
