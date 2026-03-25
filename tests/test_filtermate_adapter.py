"""Tests for FilterMateAdapter — connection, filtering, signals, error handling."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from narractive.core.filtermate_adapter import FilterMateAdapter


# ---------------------------------------------------------------------------
# Init and config
# ---------------------------------------------------------------------------


class TestFilterMateAdapterInit:
    def test_defaults(self):
        fm = FilterMateAdapter()
        assert fm._config == {}
        assert fm._api is None
        assert fm._connected is False

    def test_custom_config(self):
        fm = FilterMateAdapter(config={"timeout": 10})
        assert fm._config == {"timeout": 10}

    def test_not_connected_initially(self):
        fm = FilterMateAdapter()
        assert fm.is_connected is False


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


class TestFilterMateAdapterConnection:
    def test_require_api_raises_when_not_connected(self):
        fm = FilterMateAdapter()
        with pytest.raises(RuntimeError, match="Not connected"):
            fm._require_api()

    def test_disconnect_when_not_connected(self):
        fm = FilterMateAdapter()
        # Should not raise
        fm.disconnect()
        assert fm._api is None
        assert fm._connected is False

    def test_disconnect_disconnects_signals(self):
        fm = FilterMateAdapter()
        mock_api = MagicMock()
        fm._api = mock_api
        fm._connected = True

        fm.disconnect()

        mock_api.filter_applied.disconnect.assert_called_once()
        mock_api.filter_cleared.disconnect.assert_called_once()
        mock_api.error_occurred.disconnect.assert_called_once()
        assert fm._api is None
        assert fm._connected is False

    def test_disconnect_ignores_signal_errors(self):
        fm = FilterMateAdapter()
        mock_api = MagicMock()
        mock_api.filter_applied.disconnect.side_effect = TypeError
        fm._api = mock_api
        fm._connected = True

        # Should not raise
        fm.disconnect()
        assert fm._api is None

    def test_connect_no_qgis(self):
        """connect() returns False when qgis.utils is not importable."""
        fm = FilterMateAdapter()
        with patch.dict("sys.modules", {"qgis": None, "qgis.utils": None}):
            result = fm.connect()
        assert result is False
        assert fm.is_connected is False

    def test_connect_plugin_not_loaded(self):
        """connect() returns False when filter_mate not in plugins dict."""
        fm = FilterMateAdapter()
        mock_qgis_utils = MagicMock()
        mock_qgis_utils.plugins = {}
        with patch.dict("sys.modules", {"qgis": MagicMock(), "qgis.utils": mock_qgis_utils}):
            result = fm.connect()
        assert result is False

    def test_connect_plugin_no_public_api(self):
        """connect() returns False when plugin lacks get_public_api."""
        fm = FilterMateAdapter()
        mock_plugin = MagicMock(spec=[])  # spec=[] means no attributes
        mock_qgis_utils = MagicMock()
        mock_qgis_utils.plugins = {"filter_mate": mock_plugin}
        with patch.dict("sys.modules", {"qgis": MagicMock(), "qgis.utils": mock_qgis_utils}):
            result = fm.connect()
        assert result is False

    def test_connect_success(self):
        """connect() returns True and wires signals when plugin is available."""
        fm = FilterMateAdapter()
        mock_api = MagicMock()
        mock_api.get_version.return_value = "5.0.0"

        mock_plugin = MagicMock()
        mock_plugin.get_public_api.return_value = mock_api

        mock_qgis_utils = MagicMock()
        mock_qgis_utils.plugins = {"filter_mate": mock_plugin}

        with patch.dict("sys.modules", {"qgis": MagicMock(), "qgis.utils": mock_qgis_utils}):
            result = fm.connect()

        assert result is True
        assert fm.is_connected is True
        assert fm._api is mock_api
        mock_api.filter_applied.connect.assert_called_once()
        mock_api.filter_cleared.connect.assert_called_once()
        mock_api.error_occurred.connect.assert_called_once()

    def test_context_manager_calls_connect_disconnect(self):
        fm = FilterMateAdapter()
        fm.connect = MagicMock(return_value=True)
        fm.disconnect = MagicMock()
        with fm:
            fm.connect.assert_called_once()
        fm.disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# Filtering operations
# ---------------------------------------------------------------------------


class TestFilterMateAdapterFiltering:
    @pytest.fixture()
    def connected_adapter(self):
        """Return an adapter with a mocked, connected API."""
        fm = FilterMateAdapter()
        fm._api = MagicMock()
        fm._connected = True
        return fm

    def test_apply_filter_success(self, connected_adapter):
        fm = connected_adapter
        fm._api.apply_filter.return_value = True

        result = fm.apply_filter("routes", "type = 'primary'")

        assert result is True
        fm._api.apply_filter.assert_called_once_with(
            "routes", "type = 'primary'", source_plugin="narractive"
        )

    def test_apply_filter_custom_source(self, connected_adapter):
        fm = connected_adapter
        fm._api.apply_filter.return_value = True

        fm.apply_filter("routes", "id > 100", source_plugin="my_plugin")

        fm._api.apply_filter.assert_called_once_with(
            "routes", "id > 100", source_plugin="my_plugin"
        )

    def test_apply_filter_not_connected(self):
        fm = FilterMateAdapter()
        with pytest.raises(RuntimeError, match="Not connected"):
            fm.apply_filter("routes", "type = 'primary'")

    def test_apply_filter_api_exception(self, connected_adapter):
        fm = connected_adapter
        fm._api.apply_filter.side_effect = RuntimeError("boom")

        result = fm.apply_filter("routes", "type = 'primary'")

        assert result is False

    def test_clear_filter_success(self, connected_adapter):
        fm = connected_adapter
        fm._api.clear_filter.return_value = True

        result = fm.clear_filter("routes")

        assert result is True
        fm._api.clear_filter.assert_called_once_with("routes")

    def test_clear_filter_not_connected(self):
        fm = FilterMateAdapter()
        with pytest.raises(RuntimeError, match="Not connected"):
            fm.clear_filter("routes")

    def test_clear_all_filters_success(self, connected_adapter):
        fm = connected_adapter
        fm._api.clear_all_filters.return_value = 3

        result = fm.clear_all_filters()

        assert result == 3

    def test_clear_all_filters_not_connected(self):
        fm = FilterMateAdapter()
        with pytest.raises(RuntimeError, match="Not connected"):
            fm.clear_all_filters()

    def test_get_active_filters_connected(self, connected_adapter):
        fm = connected_adapter
        fm._api.get_active_filters.return_value = {
            "routes": "type = 'primary'",
            "batiments": "height > 10",
        }

        result = fm.get_active_filters()

        assert result == {
            "routes": "type = 'primary'",
            "batiments": "height > 10",
        }

    def test_get_active_filters_not_connected(self):
        fm = FilterMateAdapter()
        result = fm.get_active_filters()
        assert result == {}

    def test_get_version(self, connected_adapter):
        fm = connected_adapter
        fm._api.get_version.return_value = "5.1.0"

        assert fm.get_version() == "5.1.0"


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------


class TestFilterMateAdapterSignals:
    def test_on_filter_applied_logs(self, caplog):
        fm = FilterMateAdapter()
        with caplog.at_level("INFO"):
            fm._on_filter_applied("routes", "type = 'primary'")
        assert "filter applied on 'routes'" in caplog.text

    def test_on_filter_cleared_logs(self, caplog):
        fm = FilterMateAdapter()
        with caplog.at_level("INFO"):
            fm._on_filter_cleared("routes")
        assert "filter cleared on 'routes'" in caplog.text

    def test_on_error_logs(self, caplog):
        fm = FilterMateAdapter()
        with caplog.at_level("ERROR"):
            fm._on_error("something broke")
        assert "something broke" in caplog.text
