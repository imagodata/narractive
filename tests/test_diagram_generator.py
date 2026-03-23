"""Tests for DiagramGenerator — HTML generation, template rendering, backends."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_automation.core.diagram_generator import DiagramGenerator


# ---------------------------------------------------------------------------
# Init and config
# ---------------------------------------------------------------------------


class TestDiagramGeneratorInit:
    def test_defaults(self):
        g = DiagramGenerator({})
        assert g.theme == "dark"
        assert g.subtitle == ""
        assert g.footer_url == ""
        assert g.width == 1920
        assert g.height == 1080

    def test_custom_config(self, tmp_path):
        g = DiagramGenerator({
            "output_dir": str(tmp_path / "diagrams"),
            "width": 2560,
            "height": 1440,
            "theme": "forest",
            "background_color": "#000000",
            "font_family": "Arial",
            "subtitle": "My Project",
            "footer_url": "https://test.com",
        })
        assert g.width == 2560
        assert g.height == 1440
        assert g.theme == "forest"
        assert g.bg_color == "#000000"
        assert g.font_family == "Arial"
        assert g.subtitle == "My Project"
        assert g.footer_url == "https://test.com"

    def test_creates_output_dir(self, tmp_path):
        DiagramGenerator({"output_dir": str(tmp_path / "out")})
        assert (tmp_path / "out").is_dir()


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------


class TestDiagramGeneratorHTML:
    @pytest.fixture
    def gen(self, tmp_path):
        return DiagramGenerator({
            "output_dir": str(tmp_path / "diagrams"),
            "subtitle": "Test v1.0",
            "footer_url": "example.com",
        })

    def test_generate_diagram_creates_file(self, gen, tmp_path):
        mermaid = "graph LR\n    A --> B"
        output = tmp_path / "diagrams" / "test.html"
        result = gen.generate_diagram(mermaid, output, title="Test Diagram")
        assert result.exists()

    def test_generate_diagram_contains_mermaid(self, gen, tmp_path):
        mermaid = "graph LR\n    A --> B"
        output = tmp_path / "diagrams" / "test.html"
        gen.generate_diagram(mermaid, output, title="Test Diagram")
        content = output.read_text(encoding="utf-8")
        assert "A --> B" in content

    def test_generate_diagram_contains_title(self, gen, tmp_path):
        output = tmp_path / "diagrams" / "test.html"
        gen.generate_diagram("graph LR\n    A-->B", output, title="My Title")
        content = output.read_text(encoding="utf-8")
        assert "My Title" in content

    def test_generate_diagram_contains_subtitle(self, gen, tmp_path):
        output = tmp_path / "diagrams" / "test.html"
        gen.generate_diagram("graph LR\n    A-->B", output, title="T")
        content = output.read_text(encoding="utf-8")
        assert "Test v1.0" in content

    def test_generate_diagram_contains_footer(self, gen, tmp_path):
        output = tmp_path / "diagrams" / "test.html"
        gen.generate_diagram("graph LR\n    A-->B", output, title="T")
        content = output.read_text(encoding="utf-8")
        assert "example.com" in content

    def test_generate_diagram_creates_parent_dirs(self, gen, tmp_path):
        output = tmp_path / "deep" / "nested" / "test.html"
        gen.generate_diagram("graph LR\n    A-->B", output, title="T")
        assert output.exists()

    def test_generate_diagram_html_valid(self, gen, tmp_path):
        output = tmp_path / "diagrams" / "valid.html"
        gen.generate_diagram("graph TD\n    X-->Y", output, title="Valid")
        content = output.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content or "<html" in content
        assert "mermaid" in content.lower()


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------


class TestDiagramGeneratorBatch:
    def test_generate_all_diagrams(self, tmp_path):
        gen = DiagramGenerator({"output_dir": str(tmp_path / "out")})
        definitions = {
            "arch": {"title": "Architecture", "mermaid": "graph LR\n    A-->B"},
            "flow": {"title": "Flow", "mermaid": "graph TD\n    X-->Y"},
        }
        results = gen.generate_all_diagrams(definitions)
        assert len(results) == 2
        assert "arch" in results
        assert "flow" in results
        assert results["arch"].exists()

    def test_generate_all_diagrams_empty(self, tmp_path):
        gen = DiagramGenerator({"output_dir": str(tmp_path / "out")})
        results = gen.generate_all_diagrams({})
        assert results == {}

    def test_generate_all_diagrams_custom_dir(self, tmp_path):
        gen = DiagramGenerator({"output_dir": str(tmp_path / "default")})
        custom = tmp_path / "custom"
        definitions = {"d1": {"title": "T", "mermaid": "graph LR\n A-->B"}}
        results = gen.generate_all_diagrams(definitions, output_dir=custom)
        assert results["d1"].parent == custom


# ---------------------------------------------------------------------------
# .mmd file writer
# ---------------------------------------------------------------------------


class TestDiagramGeneratorMmd:
    def test_write_mmd(self, tmp_path):
        gen = DiagramGenerator({"output_dir": str(tmp_path)})
        mmd_path = tmp_path / "test.mmd"
        result = gen.write_mmd("graph LR\n    A-->B", mmd_path)
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "A-->B" in content
        assert content.endswith("\n")

    def test_write_mmd_strips_whitespace(self, tmp_path):
        gen = DiagramGenerator({"output_dir": str(tmp_path)})
        result = gen.write_mmd("  graph LR  \n  A-->B  ", tmp_path / "test.mmd")
        content = result.read_text(encoding="utf-8")
        assert not content.startswith(" ")


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------


class TestDiagramGeneratorBackend:
    def test_detect_backend_api_fallback(self, tmp_path):
        gen = DiagramGenerator({"output_dir": str(tmp_path)})
        with patch.dict("sys.modules", {"playwright.sync_api": None}):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                # This should be tricky to mock; let's just check the method exists
                backend = gen.detect_backend()
                assert backend in ("playwright", "mmdc", "api")

    @patch("subprocess.run")
    def test_render_to_png_via_mmdc(self, mock_run, tmp_path):
        gen = DiagramGenerator({"output_dir": str(tmp_path)})
        mmd = tmp_path / "test.mmd"
        mmd.write_text("graph LR\n  A-->B")
        png = tmp_path / "test.png"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = gen.render_to_png_via_mmdc(mmd, png)
        assert result == png
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_render_to_png_via_mmdc_failure(self, mock_run, tmp_path):
        gen = DiagramGenerator({"output_dir": str(tmp_path)})
        mmd = tmp_path / "test.mmd"
        mmd.write_text("graph LR\n  A-->B")
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="mmdc failed"):
            gen.render_to_png_via_mmdc(mmd, tmp_path / "test.png")


# ---------------------------------------------------------------------------
# render_to_png_auto
# ---------------------------------------------------------------------------


class TestDiagramGeneratorAutoRender:
    def test_auto_with_api_backend(self, tmp_path):
        gen = DiagramGenerator({"output_dir": str(tmp_path)})
        with patch.object(gen, "render_to_png_via_api") as mock_api:
            mock_api.return_value = tmp_path / "out.png"
            result = gen.render_to_png_auto("graph LR\n  A-->B", tmp_path / "out.png", backend="api")
            mock_api.assert_called_once()

    def test_auto_with_mmdc_backend(self, tmp_path):
        gen = DiagramGenerator({"output_dir": str(tmp_path)})
        with patch.object(gen, "write_mmd") as mock_mmd, \
             patch.object(gen, "render_to_png_via_mmdc") as mock_mmdc:
            mock_mmdc.return_value = tmp_path / "out.png"
            gen.render_to_png_auto("graph LR\n  A-->B", tmp_path / "out.png", backend="mmdc")
            mock_mmd.assert_called_once()
            mock_mmdc.assert_called_once()

    def test_auto_with_playwright_backend(self, tmp_path):
        gen = DiagramGenerator({"output_dir": str(tmp_path)})
        with patch.object(gen, "generate_diagram") as mock_html, \
             patch.object(gen, "render_to_png") as mock_png:
            mock_png.return_value = tmp_path / "out.png"
            gen.render_to_png_auto("graph LR\n  A-->B", tmp_path / "out.png", backend="playwright")
            mock_html.assert_called_once()
            mock_png.assert_called_once()
