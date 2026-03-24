"""
Tests for HybridController — PyQGIS API + PyAutoGUI mouse positioning.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers — mock PyQGIS and pyautogui before importing
# ---------------------------------------------------------------------------

def _make_qgis_mock():
    """Return a minimal qgis.core mock with the symbols we rely on."""
    qgis_core = MagicMock()
    extent = MagicMock()
    extent.xMinimum.return_value = 0.0
    extent.xMaximum.return_value = 10.0
    extent.yMinimum.return_value = 0.0
    extent.yMaximum.return_value = 10.0

    canvas = MagicMock()
    canvas.extent.return_value = extent

    iface = MagicMock()
    iface.mapCanvas.return_value = canvas

    qgis_utils = MagicMock()
    qgis_utils.iface = iface

    qgis_mod = MagicMock()
    qgis_mod.core = qgis_core
    qgis_mod.utils = qgis_utils

    return qgis_mod, iface, canvas, extent


def _mock_env():
    """Patch sys.modules with minimal fakes so imports succeed."""
    qgis_mod, iface, canvas, extent = _make_qgis_mock()
    pyautogui_mock = MagicMock()
    pyautogui_mock.FAILSAFE = True
    pyautogui_mock.PAUSE = 0.0
    pyautogui_mock.easeOutQuad = lambda t: t

    mods = {
        "qgis": qgis_mod,
        "qgis.core": qgis_mod.core,
        "qgis.utils": qgis_mod.utils,
        "pyautogui": pyautogui_mock,
    }
    return mods, iface, canvas, extent


# ---------------------------------------------------------------------------
# HybridController tests
# ---------------------------------------------------------------------------

class TestHybridControllerGeoToScreen:
    """Unit tests for the geo→screen coordinate conversion."""

    def test_centre_maps_to_canvas_centre(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {
                "qgis": {
                    "canvas_region": {"x": 0, "y": 0, "width": 100, "height": 100}
                }
            }
            ctrl = HybridController(config)

            # Geo centre (5,5) in a 0–10 extent → screen (50, 50)
            result = ctrl._geo_to_screen(5.0, 5.0)
            assert result == (50, 50), f"Expected (50, 50), got {result}"

    def test_top_left_geo_maps_to_top_left_screen(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {
                "qgis": {
                    "canvas_region": {"x": 0, "y": 0, "width": 100, "height": 100}
                }
            }
            ctrl = HybridController(config)

            # Geo (0, 10) = top-left → screen (0, 0)
            result = ctrl._geo_to_screen(0.0, 10.0)
            assert result == (0, 0), f"Expected (0, 0), got {result}"

    def test_bottom_right_geo_maps_to_bottom_right_screen(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {
                "qgis": {
                    "canvas_region": {"x": 0, "y": 0, "width": 100, "height": 100}
                }
            }
            ctrl = HybridController(config)

            # Geo (10, 0) = bottom-right → screen (100, 100)
            result = ctrl._geo_to_screen(10.0, 0.0)
            assert result == (100, 100), f"Expected (100, 100), got {result}"

    def test_out_of_bounds_geo_clamped_to_canvas(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {
                "qgis": {
                    "canvas_region": {"x": 0, "y": 0, "width": 100, "height": 100}
                }
            }
            ctrl = HybridController(config)

            # Out-of-extent geo point must clamp to canvas edge
            result = ctrl._geo_to_screen(20.0, 20.0)
            assert result == (100, 0)

    def test_canvas_region_offset_applied(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {
                "qgis": {
                    "canvas_region": {"x": 320, "y": 60, "width": 200, "height": 200}
                }
            }
            ctrl = HybridController(config)

            # Geo centre (5,5) → normalised (0.5, 0.5) → screen (320+100, 60+100)
            result = ctrl._geo_to_screen(5.0, 5.0)
            assert result == (420, 160), f"Expected (420, 160), got {result}"

    def test_no_canvas_region_returns_none(self):
        mods, iface, canvas, extent = _mock_env()
        # Remove iface so we test the canvas_region=None path
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {"qgis": {}}  # no canvas_region
            ctrl = HybridController(config)
            result = ctrl._geo_to_screen(5.0, 5.0)
            assert result is None


class TestHybridControllerMouseMethods:
    """Verify that mouse positioning methods delegate to AppAutomator."""

    def test_point_at_map_coordinate_calls_move_mouse(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {
                "qgis": {
                    "canvas_region": {"x": 0, "y": 0, "width": 100, "height": 100}
                }
            }
            ctrl = HybridController(config)
            ctrl._automator.move_mouse_to = MagicMock()
            ctrl._automator.wait = MagicMock()

            ctrl.point_at_map_coordinate(5.0, 5.0, hover=0)

            ctrl._automator.move_mouse_to.assert_called_once_with(50, 50, duration=None)

    def test_point_at_map_coordinate_list_calls_multiple(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {
                "qgis": {
                    "canvas_region": {"x": 0, "y": 0, "width": 100, "height": 100}
                }
            }
            ctrl = HybridController(config)
            ctrl._automator.move_mouse_to = MagicMock()
            ctrl._automator.wait = MagicMock()

            ctrl.point_at_map_coordinate_list(
                [(2.0, 8.0), (5.0, 5.0), (8.0, 2.0)], dwell=0
            )

            assert ctrl._automator.move_mouse_to.call_count == 3

    def test_hover_region_delegates(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {"qgis": {}}
            ctrl = HybridController(config)
            ctrl._automator.hover_region = MagicMock()

            ctrl.hover_region("layers_panel", duration=1.0)

            ctrl._automator.hover_region.assert_called_once_with("layers_panel", duration=1.0)


class TestHybridControllerQGISMethods:
    """Verify PyQGIS API methods delegate to QGISBridge."""

    def test_load_layer_delegates_to_bridge(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {"qgis": {}}
            ctrl = HybridController(config)
            ctrl._bridge.load_vector_layer = MagicMock(return_value="layer_obj")

            result = ctrl.load_layer("/data/x.shp", "X")

            ctrl._bridge.load_vector_layer.assert_called_once_with("/data/x.shp", "X")
            assert result == "layer_obj"

    def test_select_features_delegates_to_bridge(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {"qgis": {}}
            ctrl = HybridController(config)
            ctrl._bridge.select_features = MagicMock(return_value=42)

            count = ctrl.select_features("mock_layer", '"pop" > 1000')

            assert count == 42
            ctrl._bridge.select_features.assert_called_once()

    def test_run_algorithm_delegates_to_bridge(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_hybrid import HybridController

            config = {"qgis": {}}
            ctrl = HybridController(config)
            ctrl._bridge.run_algorithm = MagicMock(return_value={"OUTPUT": "x.shp"})

            result = ctrl.run_algorithm("native:buffer", {"DISTANCE": 100})

            assert result == {"OUTPUT": "x.shp"}


class TestCreateControllerHybridMode:
    """create_controller factory should return HybridController for mode=hybrid."""

    def test_factory_hybrid_mode(self):
        mods, iface, canvas, extent = _mock_env()
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_controller import create_controller
            from narractive.core.qgis_hybrid import HybridController

            config = {"qgis": {"mode": "hybrid"}}
            ctrl = create_controller(config)
            assert isinstance(ctrl, HybridController)

    def test_factory_unknown_mode_raises(self):
        mods, iface, canvas, extent = _mock_env()
        import pytest
        with patch.dict(sys.modules, mods):
            from narractive.core.qgis_controller import create_controller

            with pytest.raises(ValueError, match="Unknown QGIS controller mode"):
                create_controller({"qgis": {"mode": "invalid"}})
