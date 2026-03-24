"""
Tests Sprint 6 — QGIS controller, bridge, headless renderer, snapshot API.

PyQGIS is not installed in the test environment, so all qgis.* imports
are mocked at module level where needed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_qgis_mock() -> dict[str, ModuleType]:
    """Return a minimal sys.modules patch for qgis.* imports."""
    qgis = ModuleType("qgis")
    qgis_core = ModuleType("qgis.core")
    qgis_utils = ModuleType("qgis.utils")
    qgis_pyqt = ModuleType("qgis.PyQt")
    qgis_pyqt_core = ModuleType("qgis.PyQt.QtCore")
    qgis_pyqt_gui = ModuleType("qgis.PyQt.QtGui")
    processing = ModuleType("processing")

    # QgsProject singleton
    project = MagicMock()
    project.mapLayers.return_value = {}
    project.mapLayersByName.return_value = []
    project.layerTreeRoot.return_value = MagicMock(findLayers=lambda: [])
    project.fileName.return_value = "/tmp/test.qgz"
    project.read.return_value = True
    project.write.return_value = True
    QgsProject = MagicMock()
    QgsProject.instance.return_value = project

    qgis_core.QgsProject = QgsProject
    qgis_core.QgsVectorLayer = MagicMock(return_value=MagicMock(isValid=lambda: True))
    qgis_core.QgsRasterLayer = MagicMock(return_value=MagicMock(isValid=lambda: True))
    qgis_core.QgsRectangle = MagicMock()
    qgis_core.QgsExpression = MagicMock()
    qgis_core.QgsFeatureRequest = MagicMock()
    qgis_core.QgsCoordinateReferenceSystem = MagicMock()
    qgis_core.QgsApplication = MagicMock(instance=MagicMock(return_value=None))
    qgis_core.QgsMapSettings = MagicMock()
    qgis_core.QgsMapRendererParallelJob = MagicMock(
        return_value=MagicMock(
            start=MagicMock(),
            waitForFinished=MagicMock(),
            renderedImage=MagicMock(
                return_value=MagicMock(save=MagicMock(return_value=True))
            ),
        )
    )
    qgis_core.QgsLayoutExporter = MagicMock()

    # iface
    canvas = MagicMock()
    canvas.extent.return_value = MagicMock(
        xMinimum=lambda: 0.0,
        yMinimum=lambda: 0.0,
        xMaximum=lambda: 1.0,
        yMaximum=lambda: 1.0,
    )
    canvas.mapSettings.return_value = MagicMock(
        destinationCrs=MagicMock(return_value=MagicMock(authid=lambda: "EPSG:4326"))
    )
    iface = MagicMock()
    iface.mapCanvas.return_value = canvas
    qgis_utils.iface = iface

    qgis_pyqt_core.QSize = MagicMock()

    processing.run = MagicMock(return_value={"OUTPUT": "mock"})

    return {
        "qgis": qgis,
        "qgis.core": qgis_core,
        "qgis.utils": qgis_utils,
        "qgis.PyQt": qgis_pyqt,
        "qgis.PyQt.QtCore": qgis_pyqt_core,
        "qgis.PyQt.QtGui": qgis_pyqt_gui,
        "processing": processing,
    }


# ---------------------------------------------------------------------------
# QGISBridge
# ---------------------------------------------------------------------------


class TestQGISBridge:
    def test_raises_importerror_without_pyqgis(self) -> None:
        """QGISBridge() should raise ImportError when qgis.core is missing."""
        from video_automation.core import qgis_bridge

        with patch.dict(sys.modules, {"qgis": None, "qgis.core": None}):
            # Force re-check by patching _check_pyqgis behaviour
            import importlib

            with pytest.raises((ImportError, SystemError)):
                # Instantiate fresh to trigger the import check
                obj = object.__new__(qgis_bridge.QGISBridge)
                qgis_bridge.QGISBridge._check_pyqgis(obj)

    def test_load_vector_layer_with_mock(self) -> None:
        mocks = _make_qgis_mock()
        with patch.dict(sys.modules, mocks):
            from video_automation.core import qgis_bridge
            import importlib

            importlib.reload(qgis_bridge)
            bridge = object.__new__(qgis_bridge.QGISBridge)
            layer = bridge.load_vector_layer("/tmp/test.gpkg", "regions")
            assert layer is not None

    def test_get_project_layers_with_mock(self) -> None:
        mocks = _make_qgis_mock()
        with patch.dict(sys.modules, mocks):
            from video_automation.core import qgis_bridge
            import importlib

            importlib.reload(qgis_bridge)
            bridge = object.__new__(qgis_bridge.QGISBridge)
            layers = bridge.get_project_layers()
            assert isinstance(layers, list)

    def test_run_algorithm_with_mock(self) -> None:
        mocks = _make_qgis_mock()
        with patch.dict(sys.modules, mocks):
            from video_automation.core import qgis_bridge
            import importlib

            importlib.reload(qgis_bridge)
            bridge = object.__new__(qgis_bridge.QGISBridge)
            result = bridge.run_algorithm("native:buffer", {"DISTANCE": 100})
            assert result == {"OUTPUT": "mock"}


# ---------------------------------------------------------------------------
# HeadlessRenderer
# ---------------------------------------------------------------------------


class TestHeadlessRenderer:
    def test_raises_importerror_without_pyqgis(self) -> None:
        with patch.dict(sys.modules, {"qgis": None, "qgis.core": None}):
            import importlib
            from video_automation.core import qgis_headless

            importlib.reload(qgis_headless)
            with pytest.raises((ImportError, SystemError)):
                qgis_headless._bootstrap_qgis()

    def test_render_calls_qgis_renderer(self, tmp_path: Path) -> None:
        mocks = _make_qgis_mock()
        import importlib
        # Pre-import the module so it's in sys.modules before patching
        import video_automation.core.qgis_headless as qgis_headless

        with patch.dict(sys.modules, mocks):
            importlib.reload(qgis_headless)
            renderer = object.__new__(qgis_headless.HeadlessRenderer)
            renderer.prefix_path = None

            out = tmp_path / "map.png"
            result = renderer.render("/tmp/test.qgz", out)
            assert result == out


# ---------------------------------------------------------------------------
# QGISSnapshot (no PyQGIS needed for save/load/list)
# ---------------------------------------------------------------------------


class TestQGISSnapshot:
    def test_save_and_load(self, tmp_path: Path) -> None:
        from video_automation.core.qgis_snapshot import QGISSnapshot

        data = {
            "project_path": "/tmp/p.qgz",
            "crs_epsg": "EPSG:4326",
            "extent": {"xmin": 0, "ymin": 0, "xmax": 1, "ymax": 1},
            "layers": [],
        }
        snap = QGISSnapshot(data)
        out = tmp_path / "snapshots" / "scene_A.json"
        snap.save(out)

        assert out.exists()
        loaded = QGISSnapshot.load(out)
        assert loaded.data["project_path"] == "/tmp/p.qgz"
        assert loaded.data["crs_epsg"] == "EPSG:4326"

    def test_list_snapshots_empty_dir(self, tmp_path: Path) -> None:
        from video_automation.core.qgis_snapshot import QGISSnapshot

        snaps = QGISSnapshot.list_snapshots(tmp_path / "no_such_dir")
        assert snaps == []

    def test_list_snapshots_returns_json_files(self, tmp_path: Path) -> None:
        from video_automation.core.qgis_snapshot import QGISSnapshot

        snap_dir = tmp_path / "snapshots"
        snap_dir.mkdir()
        (snap_dir / "a.json").write_text("{}")
        (snap_dir / "b.json").write_text("{}")
        (snap_dir / "notes.txt").write_text("ignore")

        snaps = QGISSnapshot.list_snapshots(snap_dir)
        assert len(snaps) == 2
        assert all(p.suffix == ".json" for p in snaps)

    def test_capture_raises_without_qgis(self) -> None:
        from video_automation.core.qgis_snapshot import QGISSnapshot

        with patch.dict(sys.modules, {"qgis": None, "qgis.core": None, "qgis.utils": None}):
            with pytest.raises((ImportError, SystemError)):
                QGISSnapshot.capture()

    def test_snapshot_dir(self) -> None:
        from video_automation.core.qgis_snapshot import QGISSnapshot

        d = QGISSnapshot.snapshot_dir("/project")
        assert str(d).endswith("diagrams/snapshots")

    def test_save_json_is_readable(self, tmp_path: Path) -> None:
        from video_automation.core.qgis_snapshot import QGISSnapshot

        data = {"project_path": "/x", "crs_epsg": "EPSG:2154", "extent": {}, "layers": []}
        snap = QGISSnapshot(data)
        out = tmp_path / "snap.json"
        snap.save(out)
        raw = json.loads(out.read_text())
        assert raw["crs_epsg"] == "EPSG:2154"


# ---------------------------------------------------------------------------
# QGISController / create_controller
# ---------------------------------------------------------------------------


class TestQGISController:
    def test_detect_mode_returns_pyautogui_without_qgis(self) -> None:
        with patch.dict(sys.modules, {"qgis": None, "qgis.core": None, "qgis.utils": None}):
            import importlib
            from video_automation.core import qgis_controller

            importlib.reload(qgis_controller)
            mode = qgis_controller._detect_mode()
            assert mode == "pyautogui"

    def test_create_controller_unknown_mode_raises(self) -> None:
        from video_automation.core.qgis_controller import create_controller

        with pytest.raises(ValueError, match="Unknown QGIS mode"):
            create_controller({"qgis": {"mode": "invalid_mode"}})

    def test_create_controller_pyautogui_mode(self) -> None:
        mock_automator_cls = MagicMock()
        mock_automator_cls.return_value = MagicMock()

        with patch(
            "video_automation.core.qgis_controller.AutoGUIController.__init__",
            return_value=None,
        ):
            from video_automation.core.qgis_controller import (
                AutoGUIController,
                create_controller,
            )

            ctrl = create_controller({"qgis": {"mode": "pyautogui"}})
            assert isinstance(ctrl, AutoGUIController)

    def test_create_controller_auto_fallback_to_pyautogui(self) -> None:
        with patch.dict(sys.modules, {"qgis": None, "qgis.core": None, "qgis.utils": None}):
            import importlib
            from video_automation.core import qgis_controller

            importlib.reload(qgis_controller)

            with patch.object(qgis_controller, "_detect_mode", return_value="pyautogui"):
                with patch(
                    "video_automation.core.qgis_controller.AutoGUIController.__init__",
                    return_value=None,
                ):
                    ctrl = qgis_controller.create_controller({"qgis": {"mode": "auto"}})
                    assert isinstance(ctrl, qgis_controller.AutoGUIController)

    def test_controller_get_mode(self) -> None:
        with patch(
            "video_automation.core.qgis_controller.AutoGUIController.__init__",
            return_value=None,
        ):
            from video_automation.core.qgis_controller import AutoGUIController

            ctrl = object.__new__(AutoGUIController)
            assert ctrl.get_mode() == "AutoGUIController"


# ---------------------------------------------------------------------------
# Config schema — QGISConfig
# ---------------------------------------------------------------------------


class TestQGISConfig:
    def test_qgis_config_defaults(self) -> None:
        from video_automation.config_schema import is_pydantic_available

        if not is_pydantic_available():
            pytest.skip("pydantic not installed")

        from video_automation.config_schema import NarractiveConfig

        cfg = NarractiveConfig()
        assert cfg.qgis.mode == "auto"
        assert cfg.qgis.prefix_path is None
        assert cfg.qgis.project_path is None

    def test_qgis_config_custom(self) -> None:
        from video_automation.config_schema import is_pydantic_available

        if not is_pydantic_available():
            pytest.skip("pydantic not installed")

        from video_automation.config_schema import NarractiveConfig

        cfg = NarractiveConfig.model_validate(
            {"qgis": {"mode": "headless", "prefix_path": "/usr/local"}}
        )
        assert cfg.qgis.mode == "headless"
        assert cfg.qgis.prefix_path == "/usr/local"


# ---------------------------------------------------------------------------
# CLI — snapshot commands
# ---------------------------------------------------------------------------


class TestCLISnapshot:
    def test_snapshot_list_empty(self, tmp_path: Path) -> None:
        from video_automation.cli import cli

        runner = CliRunner()
        result = runner.invoke(
            cli, ["snapshot", "list", "--dir", str(tmp_path / "no_snaps")]
        )
        assert result.exit_code == 0
        assert "No snapshots" in result.output

    def test_snapshot_list_with_files(self, tmp_path: Path) -> None:
        from video_automation.cli import cli

        snap_dir = tmp_path / "snaps"
        snap_dir.mkdir()
        (snap_dir / "scene_A.json").write_text("{}")
        (snap_dir / "scene_B.json").write_text("{}")

        runner = CliRunner()
        result = runner.invoke(cli, ["snapshot", "list", "--dir", str(snap_dir)])
        assert result.exit_code == 0
        assert "scene_A" in result.output
        assert "scene_B" in result.output

    def test_snapshot_restore_missing_file(self, tmp_path: Path) -> None:
        from video_automation.cli import cli

        runner = CliRunner()
        result = runner.invoke(
            cli, ["snapshot", "restore", "nonexistent", "--dir", str(tmp_path)]
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# CLI — qgis-plugin commands
# ---------------------------------------------------------------------------


class TestCLIQGISPlugin:
    def test_qgis_plugin_install_help(self) -> None:
        from video_automation.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["qgis-plugin", "install", "--help"])
        assert result.exit_code == 0
        assert "qgis-plugins-dir" in result.output

    def test_qgis_plugin_install_copies_files(self, tmp_path: Path) -> None:
        from video_automation.cli import cli

        dest = tmp_path / "plugins"
        runner = CliRunner()
        result = runner.invoke(
            cli, ["qgis-plugin", "install", "--qgis-plugins-dir", str(dest)]
        )
        assert result.exit_code == 0, result.output
        assert (dest / "narractive" / "metadata.txt").exists()
        assert (dest / "narractive" / "__init__.py").exists()
        assert (dest / "narractive" / "plugin_main.py").exists()
