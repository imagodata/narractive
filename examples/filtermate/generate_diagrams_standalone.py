#!/usr/bin/env python3
"""
Diagram generator for FilterMate — creates HTML + PNG from Mermaid definitions.
Thin wrapper around video_automation.core.diagram_generator.

No OBS required. Just Python + Playwright (optional for PNG).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

from diagrams.mermaid_definitions import DIAGRAMS
from video_automation.core.diagram_generator import DiagramGenerator

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "diagrams")

DIAGRAM_CONFIG = {
    "output_dir": OUTPUT_DIR,
    "width": 1920,
    "height": 1080,
    "theme": "dark",
    "background_color": "#1a1a2e",
    "font_family": "Segoe UI",
    "subtitle": "FilterMate v4.6.1",
    "footer_url": "github.com/imagodata/filter_mate",
}


def main():
    gen = DiagramGenerator(DIAGRAM_CONFIG)

    print(f"\n{'='*50}")
    print(f"  FilterMate Diagram Generator")
    print(f"  {len(DIAGRAMS)} diagrams to generate")
    print(f"{'='*50}\n")

    html_count = 0
    png_count = 0

    for diagram_id, diagram_data in DIAGRAMS.items():
        title = diagram_data["title"]
        mermaid_code = diagram_data["mermaid"]
        print(f"  [{diagram_id}] {title}")

        html_path = gen.generate_diagram(
            mermaid_code,
            os.path.join(OUTPUT_DIR, "html", f"{diagram_id}.html"),
            title=title,
        )
        html_count += 1
        print(f"    ✓ HTML: {html_path}")

        png_path = os.path.join(OUTPUT_DIR, "png", f"{diagram_id}.png")
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        try:
            gen.render_to_png(str(html_path), png_path)
            png_count += 1
            print(f"    ✓ PNG: {png_path}")
        except Exception:
            pass  # Warning already logged by render_to_png

    print(f"\n  Done: {html_count} HTML files")
    if png_count > 0:
        print(f"        {png_count} PNG files")
    else:
        print("        PNG rendering skipped (install Playwright for PNG)")
    print()


if __name__ == "__main__":
    main()
