"""
FilterMate Adapter
==================
Controls the FilterMate QGIS plugin via its public API (direct Qt calls).

Usage:
    from narractive.core.filtermate_adapter import FilterMateAdapter

    fm = FilterMateAdapter()
    fm.connect()
    fm.apply_filter("routes", "type = 'primary'")
    fm.clear_filters()

Notes
-----
- Requires FilterMate >= 5.0 with ``get_public_api()`` support.
- Must run inside a QGIS session (``qgis.utils.plugins`` available).
- Falls back gracefully when FilterMate is not loaded.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FilterMateAdapter:
    """
    Bridge to the FilterMate QGIS plugin via its public API.

    Parameters
    ----------
    config : dict, optional
        The 'filtermate' section from config.yaml.
    """

    def __init__(self, config: dict | None = None) -> None:
        self._config = config or {}
        self._api: Any = None
        self._connected: bool = False

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "FilterMateAdapter":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.disconnect()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Return True if connected to FilterMate and API is available."""
        return self._connected and self._api is not None

    def connect(self) -> bool:
        """
        Attempt to connect to the FilterMate plugin.

        Returns
        -------
        bool
            True if connection succeeded.
        """
        try:
            from qgis.utils import plugins  # type: ignore
        except ImportError:
            logger.warning("qgis.utils not available — not running inside QGIS")
            return False

        if "filter_mate" not in plugins:
            logger.warning("FilterMate plugin not loaded in QGIS")
            return False

        plugin = plugins["filter_mate"]
        if not hasattr(plugin, "get_public_api"):
            logger.warning(
                "FilterMate version too old — no public API (need >= 5.0)"
            )
            return False

        try:
            self._api = plugin.get_public_api()
            self._connected = True

            # Connect signals for logging
            self._api.filter_applied.connect(self._on_filter_applied)
            self._api.filter_cleared.connect(self._on_filter_cleared)
            self._api.error_occurred.connect(self._on_error)

            version = self._api.get_version()
            logger.info("Connected to FilterMate %s", version)
            return True

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to connect to FilterMate: %s", exc)
            self._api = None
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from FilterMate signals and release the API handle."""
        if self._api is not None:
            try:
                self._api.filter_applied.disconnect(self._on_filter_applied)
                self._api.filter_cleared.disconnect(self._on_filter_cleared)
                self._api.error_occurred.disconnect(self._on_error)
            except (TypeError, RuntimeError):
                pass
        self._api = None
        self._connected = False
        logger.info("Disconnected from FilterMate.")

    def _require_api(self) -> Any:
        if not self.is_connected:
            raise RuntimeError(
                "Not connected to FilterMate. Call connect() first."
            )
        return self._api

    # ------------------------------------------------------------------
    # Filtering operations
    # ------------------------------------------------------------------

    def apply_filter(
        self, layer_name: str, expression: str, source_plugin: str = "narractive"
    ) -> bool:
        """
        Apply a filter expression to a layer.

        Parameters
        ----------
        layer_name : str
            Name of the QGIS layer to filter.
        expression : str
            QGIS filter expression string.
        source_plugin : str
            Identifies the caller (for FilterMate audit/logging).

        Returns
        -------
        bool
            True if the filter was applied successfully.
        """
        api = self._require_api()
        try:
            result = api.apply_filter(
                layer_name, expression, source_plugin=source_plugin
            )
            logger.info(
                "Applied filter on '%s': %s", layer_name, expression
            )
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to apply filter on '%s': %s", layer_name, exc
            )
            return False

    def clear_filter(self, layer_name: str) -> bool:
        """
        Clear the filter on a specific layer.

        Parameters
        ----------
        layer_name : str
            Name of the QGIS layer.

        Returns
        -------
        bool
            True if the filter was cleared.
        """
        api = self._require_api()
        try:
            result = api.clear_filter(layer_name)
            logger.info("Cleared filter on '%s'", layer_name)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to clear filter on '%s': %s", layer_name, exc
            )
            return False

    def clear_all_filters(self) -> int:
        """
        Clear all active filters.

        Returns
        -------
        int
            Number of filters cleared.
        """
        api = self._require_api()
        try:
            count = api.clear_all_filters()
            logger.info("Cleared %d active filters", count)
            return count
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to clear all filters: %s", exc)
            return 0

    def get_active_filters(self) -> dict[str, str]:
        """
        Get all currently active filters.

        Returns
        -------
        dict
            Mapping of ``{layer_name: expression}`` for active filters.
        """
        if not self.is_connected:
            return {}
        try:
            return self._api.get_active_filters()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to get active filters: %s", exc)
            return {}

    def get_version(self) -> str:
        """Return the FilterMate plugin version string."""
        api = self._require_api()
        return api.get_version()

    # ------------------------------------------------------------------
    # Signal handlers (logging)
    # ------------------------------------------------------------------

    def _on_filter_applied(self, layer_name: str, expression: str) -> None:
        logger.info(
            "FilterMate signal: filter applied on '%s': %s",
            layer_name,
            expression,
        )

    def _on_filter_cleared(self, layer_name: str) -> None:
        logger.info(
            "FilterMate signal: filter cleared on '%s'", layer_name
        )

    def _on_error(self, error_msg: str) -> None:
        logger.error("FilterMate signal: error — %s", error_msg)
