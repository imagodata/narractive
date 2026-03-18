"""Tests for DiagramGenerator (HTML generation, template rendering)."""
from __future__ import annotations

from pathlib import Path

import pytest

from video_automation.core.diagram_generator import DiagramGenerator


@pytest.fixture
def gen(tmp_path):
    """Create a DiagramGenerator pointed at a temp directory."""
    return DiagramGenerator({
        "output_dir": str(tmp_path / "diagrams"),
        "width": 1920,
        "height": 1080,
        "theme": "dark",
        "background_color": "#1a1a2e",
        "font_family": "Segoe UI",
        "subtitle": "Test v1.0",
        "footer_url": "example.com",
    })


class TestDiagramGenerator:
    def test_init_creates_output_dir(self, gen, tmp_path):
        assert (tmp_path / "diagrams").is_dir()

    def test_init_defaults(self):
        g = DiagramGenerator({})
        assert g.theme == "dark"
        assert g.subtitle == ""
        assert g.footer_url == ""

    def test_generate_diagram_html(self, gen, tmp_path):
        mermaid = "graph LR\n    A --> B"
        output = tmp_path / "diagrams" / "test.html"
        result = gen.generate_diagram(mermaid, output, title="Test Diagram")
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "Test Diagram" in content
        assert "A --> B" in content

    def test_generate_diagram_uses_subtitle(self, gen, tmp_path):
        mermaid = "graph LR\n    A --> B"
        output = tmp_path / "diagrams" / "test2.html"
        result = gen.generate_diagram(mermaid, output, title="Title")
        content = result.read_text(encoding="utf-8")
        assert "Test v1.0" in content

    def test_generate_diagram_uses_footer_url(self, gen, tmp_path):
        mermaid = "graph LR\n    A --> B"
        output = tmp_path / "diagrams" / "test3.html"
        result = gen.generate_diagram(mermaid, output, title="Title")
        content = result.read_text(encoding="utf-8")
        assert "example.com" in content
