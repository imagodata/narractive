"""Tests Sprint 6 — QGIS controller, bridge, headless, snapshot."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

# ---------------------------------------------------------------------------
# Helpers to mock the qgis package hierarchy
# ---------------------------------------------------------------------------

def _make_qgis_mock():
    """Return a minimal qgis mock tree covering qgis.core and qgis.utils."""
    qgis_mod = MagicMock()

    # qgis.core mocks
    core = MagicMock()
    core.QgsVectorLayer = MagicMock()
    core.QgsRasterLayer = MagicMock()
    core.QgsProject = MagicMock()
    core.QgsRectangle = MagicMock()
    core.QgsApplication = MagicMock()

    # Make QgsProject.instance() return a usable mock
    project_instance = MagicMock()
    project_instance.mapLayers.return_value = {}
    project_instance.read.return_value = True
    project_instance.write.return_value = True
    project_instance.fileName.return_value = ""
    project_instance.crs.return_value = MagicMock(isValid=lambda: False)
    project_instance.layerTreeRoot.return_value = MagicMock()
    core.QgsProject.instance.return_value = project_instance

    # Make QgsVectorLayer instances appear valid
    mock_layer = MagicMock()
    mock_layer.isValid.return_value = True
    mock_layer.name.return_value = "test_layer"
    mock_layer.selectedFeatureCount.return_value = 3
    core.QgsVectorLayer.return_value = mock_layer

    mock_raster = MagicMock()
    mock_raster.isValid.return_value = True
    core.QgsRasterLayer.return_value = mock_raster

    # qgis.utils
    utils = MagicMock()
    utils.iface = MagicMock()

    qgis_mod.core = core
    qgis_mod.utils = utils

    return qgis_mod, core, utils


# ===========================================================================
# Issue #21 — QGISBridge
# ===========================================================================


class TestQGISBridgeNoQGIS:
    """QGISBridge raises ImportError when qgis is not installed."""

    def test_load_vector_raises_import_error(self):
        # Ensure qgis is NOT importable
        with patch.dict(sys.modules, {"qgis": None, "qgis.core": None}):
            # Force reimport
            if "video_automation.core.qgis_bridge" in sys.modules:
                del sys.modules["video_automation.core.qgis_bridge"]
            from video_automation.core.qgis_bridge import QGISBridge
            bridge = QGISBridge()
            with pytest.raises(ImportError):
                bridge.load_vector_layer("/fake/path.shp", "layer")


class TestQGISBridgeWithMock:
    """QGISBridge works correctly when qgis is mocked."""

    def test_load_vector_layer(self):
        qgis_mock, core, utils = _make_qgis_mock()
        with patch.dict(sys.modules, {"qgis": qgis_mock, "qgis.core": core, "qgis.utils": utils}):
            if "video_automation.core.qgis_bridge" in sys.modules:
                del sys.modules["video_automation.core.qgis_bridge"]
            from video_automation.core.qgis_bridge import QGISBridge
            bridge = QGISBridge()
            layer = bridge.load_vector_layer("/data/roads.shp", "roads")
            assert layer is not None
            core.QgsVectorLayer.assert_called_once_with("/data/roads.shp", "roads", "ogr")

    def test_get_project_layers(self):
        qgis_mock, core, utils = _make_qgis_mock()
        core.QgsProject.instance.return_value.mapLayers.return_value = {"id1": MagicMock()}
        with patch.dict(sys.modules, {"qgis": qgis_mock, "qgis.core": core, "qgis.utils": utils}):
            if "video_automation.core.qgis_bridge" in sys.modules:
                del sys.modules["video_automation.core.qgis_bridge"]
            from video_automation.core.qgis_bridge import QGISBridge
            bridge = QGISBridge()
            layers = bridge.get_project_layers()
            assert "id1" in layers

    def test_select_features(self):
        qgis_mock, core, utils = _make_qgis_mock()
        with patch.dict(sys.modules, {"qgis": qgis_mock, "qgis.core": core, "qgis.utils": utils}):
            if "video_automation.core.qgis_bridge" in sys.modules:
                del sys.modules["video_automation.core.qgis_bridge"]
            from video_automation.core.qgis_bridge import QGISBridge
            bridge = QGISBridge()
            mock_layer = MagicMock()
            mock_layer.selectedFeatureCount.return_value = 5
            count = bridge.select_features(mock_layer, '"pop" > 1000')
            assert count == 5
            mock_layer.selectByExpression.assert_called_once_with('"pop" > 1000')


# ===========================================================================
# Issue #22 — HeadlessRenderer
# ===========================================================================


class TestHeadlessRendererNoQGIS:
    """HeadlessRenderer raises ImportError when qgis is not installed."""

    def test_init_raises_import_error(self):
        with patch.dict(sys.modules, {"qgis": None, "qgis.core": None}):
            if "video_automation.core.qgis_headless" in sys.modules:
                del sys.modules["video_automation.core.qgis_headless"]
            from video_automation.core.qgis_headless import HeadlessRenderer
            with pytest.raises(ImportError):
                HeadlessRenderer()


# ===========================================================================
# Issue #24 — QGISSnapshot (no PyQGIS required for save/load/list)
# ===========================================================================


class TestQGISSnapshotSaveLoad:
    """QGISSnapshot.save / load / list_snapshots work without PyQGIS."""

    def test_save_and_load(self, tmp_path):
        if "video_automation.core.qgis_snapshot" in sys.modules:
            del sys.modules["video_automation.core.qgis_snapshot"]
        from video_automation.core.qgis_snapshot import QGISSnapshot

        snap = QGISSnapshot(
            project_path="/project/my.qgz",
            crs_epsg=4326,
            extent={"xmin": 0.0, "ymin": 0.0, "xmax": 1.0, "ymax": 1.0},
            layers=[{"id": "l1", "name": "roads", "visible": True, "type": "vector",
                     "selected_ids": [], "filter": ""}],
        )
        out_path = tmp_path / "test_snap.json"
        saved = snap.save(str(out_path))

        loaded = QGISSnapshot.load(saved)
        assert loaded.project_path == "/project/my.qgz"
        assert loaded.crs_epsg == 4326
        assert loaded.extent["xmax"] == 1.0
        assert len(loaded.layers) == 1
        assert loaded.layers[0]["name"] == "roads"

    def test_list_snapshots_empty(self, tmp_path):
        from video_automation.core.qgis_snapshot import QGISSnapshot
        result = QGISSnapshot.list_snapshots(tmp_path)
        assert result == []

    def test_list_snapshots_finds_files(self, tmp_path):
        from video_automation.core.qgis_snapshot import QGISSnapshot

        # Create two fake snapshot files
        (tmp_path / "snap_a.json").write_text("{}")
        (tmp_path / "snap_b.json").write_text("{}")
        (tmp_path / "not_a_snapshot.txt").write_text("ignore me")

        result = QGISSnapshot.list_snapshots(tmp_path)
        names = [p.stem for p in result]
        assert "snap_a" in names
        assert "snap_b" in names
        assert "not_a_snapshot" not in names

    def test_snapshot_dir_default(self):
        from video_automation.core.qgis_snapshot import QGISSnapshot
        d = QGISSnapshot.snapshot_dir()
        assert str(d).endswith("snapshots")

    def test_snapshot_dir_with_base(self):
        from video_automation.core.qgis_snapshot import QGISSnapshot
        d = QGISSnapshot.snapshot_dir("/some/base")
        assert str(d) == "/some/base/snapshots"


class TestQGISSnapshotCaptureNoQGIS:
    """QGISSnapshot.capture() raises ImportError without PyQGIS."""

    def test_capture_raises(self):
        with patch.dict(sys.modules, {"qgis": None, "qgis.core": None}):
            if "video_automation.core.qgis_snapshot" in sys.modules:
                del sys.modules["video_automation.core.qgis_snapshot"]
            from video_automation.core.qgis_snapshot import QGISSnapshot
            with pytest.raises(ImportError):
                QGISSnapshot.capture()


# ===========================================================================
# Issue #25 — QGISController factory
# ===========================================================================


class TestQGISController:
    """create_controller() and _detect_mode() behave correctly."""

    def test_create_controller_pyautogui_mode(self):
        if "video_automation.core.qgis_controller" in sys.modules:
            del sys.modules["video_automation.core.qgis_controller"]
        # Mock pyautogui so AutoGUIController can init
        pyautogui_mock = MagicMock()
        with patch.dict(sys.modules, {"pyautogui": pyautogui_mock}):
            from video_automation.core.qgis_controller import create_controller, AutoGUIController
            ctrl = create_controller({"qgis": {"mode": "pyautogui"}})
            assert isinstance(ctrl, AutoGUIController)

    def test_create_controller_auto_without_qgis(self):
        """auto mode falls back to pyautogui when qgis is unavailable."""
        if "video_automation.core.qgis_controller" in sys.modules:
            del sys.modules["video_automation.core.qgis_controller"]
        pyautogui_mock = MagicMock()
        with patch.dict(sys.modules, {"qgis": None, "qgis.core": None, "pyautogui": pyautogui_mock}):
            from video_automation.core.qgis_controller import create_controller, AutoGUIController
            ctrl = create_controller({"qgis": {"mode": "auto"}})
            assert isinstance(ctrl, AutoGUIController)

    def test_detect_mode_returns_pyautogui_without_qgis(self):
        """_detect_mode() returns 'pyautogui' when qgis is not importable."""
        if "video_automation.core.qgis_controller" in sys.modules:
            del sys.modules["video_automation.core.qgis_controller"]
        with patch.dict(sys.modules, {"qgis": None, "qgis.core": None}):
            from video_automation.core.qgis_controller import _detect_mode
            mode = _detect_mode()
            assert mode == "pyautogui"

    def test_create_controller_unknown_mode_raises(self):
        if "video_automation.core.qgis_controller" in sys.modules:
            del sys.modules["video_automation.core.qgis_controller"]
        from video_automation.core.qgis_controller import create_controller
        with pytest.raises(ValueError, match="Unknown QGIS controller mode"):
            create_controller({"qgis": {"mode": "does_not_exist"}})


# ===========================================================================
# Config schema — QGISConfig
# ===========================================================================


class TestQGISConfig:
    """QGISConfig has correct defaults."""

    def test_qgis_config_defaults(self):
        try:
            from pydantic import BaseModel  # noqa: F401
        except ImportError:
            pytest.skip("pydantic not installed")

        from video_automation.config_schema import QGISConfig  # type: ignore
        cfg = QGISConfig()
        assert cfg.mode == "auto"
        assert cfg.prefix_path is None
        assert cfg.project_path is None

    def test_narractive_config_has_qgis(self):
        try:
            from pydantic import BaseModel  # noqa: F401
        except ImportError:
            pytest.skip("pydantic not installed")

        from video_automation.config_schema import NarractiveConfig, QGISConfig  # type: ignore
        cfg = NarractiveConfig()
        assert hasattr(cfg, "qgis")
        assert isinstance(cfg.qgis, QGISConfig)
        assert cfg.qgis.mode == "auto"

    def test_narractive_config_qgis_custom_mode(self):
        try:
            from pydantic import BaseModel  # noqa: F401
        except ImportError:
            pytest.skip("pydantic not installed")

        from video_automation.config_schema import NarractiveConfig  # type: ignore
        cfg = NarractiveConfig(qgis={"mode": "headless", "project_path": "/data/my.qgz"})
        assert cfg.qgis.mode == "headless"
        assert cfg.qgis.project_path == "/data/my.qgz"


# ===========================================================================
# CLI — snapshot group and qgis-plugin
# ===========================================================================


class TestCLISnapshotList:
    """narractive snapshot list works via Click test runner."""

    def test_snapshot_list_empty(self, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from video_automation.cli import snapshot_group

        # Point snapshot_dir to an empty tmp directory
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(snapshot_list_cmd, [])
        # Should not crash; output mentions 'No snapshots'
        assert result.exit_code == 0
        assert "No snapshots" in result.output


def _get_snapshot_list_cmd():
    """Retrieve the snapshot list subcommand."""
    from video_automation.cli import snapshot_group
    # snapshot_group.commands['list']
    for name, cmd in snapshot_group.commands.items():
        if name == "list":
            return cmd
    raise RuntimeError("snapshot list command not found")


# Use a module-level reference so the test can import it
try:
    snapshot_list_cmd = _get_snapshot_list_cmd()
except Exception:
    snapshot_list_cmd = None  # type: ignore


@pytest.mark.skipif(snapshot_list_cmd is None, reason="CLI not importable")
class TestCLISnapshotListDirect:
    def test_snapshot_list_no_dir(self, tmp_path, monkeypatch):
        from click.testing import CliRunner
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(snapshot_list_cmd, [])
        assert result.exit_code == 0
        assert "No snapshots" in result.output


class TestCLIQGISPlugin:
    """narractive qgis-plugin install shows help and options."""

    def test_qgis_plugin_help(self):
        from click.testing import CliRunner
        from video_automation.cli import cmd_qgis_plugin
        runner = CliRunner()
        result = runner.invoke(cmd_qgis_plugin, ["--help"])
        assert result.exit_code == 0
        assert "install" in result.output.lower() or "action" in result.output.lower()

    def test_qgis_plugin_install_option_present(self):
        from click.testing import CliRunner
        from video_automation.cli import cmd_qgis_plugin
        runner = CliRunner()
        result = runner.invoke(cmd_qgis_plugin, ["--help"])
        # --qgis-plugins-dir option should appear in help
        assert "qgis-plugins-dir" in result.output
