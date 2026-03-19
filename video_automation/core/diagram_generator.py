"""
Diagram Generator
=================
Converts Mermaid diagram definitions into styled HTML pages and renders
them to PNG.  Multiple rendering backends are supported:

- **Playwright** (headless Chromium) — highest quality, requires install.
- **mmdc** (mermaid-cli) — local CLI, requires Node.js + Chrome libs.
- **mermaid.ink API** — zero-dependency HTTP fallback, public API.

Usage::

    from video_automation.core.diagram_generator import DiagramGenerator
    gen = DiagramGenerator(config["diagrams"])

    # HTML + Playwright (original)
    html_path = gen.generate_diagram(mermaid_code, "out/01.html", title="Arch")
    png_path  = gen.render_to_png(html_path, "out/01.png")

    # Direct PNG via mermaid.ink API (zero-dep)
    png_path  = gen.render_to_png_via_api(mermaid_code, "out/01.png")

    # Auto-detect best backend
    png_path  = gen.render_to_png_auto(mermaid_code, "out/01.png")
"""

from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = Path(__file__).parent.parent / "diagrams" / "template.html"


class DiagramGenerator:
    """
    Generates styled HTML files from Mermaid diagram code and renders to PNG.

    Parameters
    ----------
    config : dict
        The 'diagrams' section from config.yaml.
    """

    def __init__(self, config: dict) -> None:
        self.output_dir = Path(config.get("output_dir", "output/diagrams"))
        self.width: int = config.get("width", 1920)
        self.height: int = config.get("height", 1080)
        self.theme: str = config.get("theme", "dark")
        self.bg_color: str = config.get("background_color", "#1a1a2e")
        self.font_family: str = config.get("font_family", "Segoe UI")
        self.subtitle: str = config.get("subtitle", "")
        self.footer_url: str = config.get("footer_url", "")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    def generate_diagram(
        self,
        mermaid_code: str,
        output_path: str | Path,
        title: str = "",
    ) -> Path:
        """
        Create a standalone HTML file containing the rendered Mermaid diagram.

        Parameters
        ----------
        mermaid_code : str
            The raw Mermaid diagram definition.
        output_path : str | Path
            Where to write the HTML file.
        title : str
            Title displayed at the top of the slide.

        Returns
        -------
        Path
            Path to the generated HTML file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        html = self._build_html(mermaid_code, title)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Generated diagram HTML: %s", output_path)
        return output_path

    def generate_all_diagrams(
        self,
        definitions: dict,
        output_dir: Optional[str | Path] = None,
    ) -> dict[str, Path]:
        """
        Batch-generate HTML files for all diagram definitions.

        Parameters
        ----------
        definitions : dict
            Mapping of diagram_id → {"title": str, "mermaid": str}.
        output_dir : str | Path, optional
            Override for output directory.

        Returns
        -------
        dict
            Mapping of diagram_id → Path to generated HTML file.
        """
        out_dir = Path(output_dir) if output_dir else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        results: dict[str, Path] = {}
        for diagram_id, info in definitions.items():
            title = info.get("title", diagram_id)
            mermaid = info.get("mermaid", "")
            html_path = out_dir / f"{diagram_id}.html"
            self.generate_diagram(mermaid, html_path, title=title)
            results[diagram_id] = html_path
        logger.info("Generated %d diagram HTML files in %s", len(results), out_dir)
        return results

    # ------------------------------------------------------------------
    # PNG rendering (requires Playwright)
    # ------------------------------------------------------------------

    def render_to_png(
        self,
        html_path: str | Path,
        png_path: str | Path,
        width: Optional[int] = None,
        height: Optional[int] = None,
        wait_ms: int = 2000,
    ) -> Path:
        """
        Render an HTML diagram file to PNG using Playwright (headless Chromium).

        Falls back gracefully if Playwright is not installed.

        Parameters
        ----------
        html_path : str | Path
            Path to the HTML file to render.
        png_path : str | Path
            Output PNG path.
        width, height : int, optional
            Viewport size (defaults to config values).
        wait_ms : int
            Milliseconds to wait for Mermaid to render before screenshotting.

        Returns
        -------
        Path
            Path to the PNG file.
        """
        html_path = Path(html_path).resolve()
        png_path = Path(png_path)
        png_path.parent.mkdir(parents=True, exist_ok=True)
        w = width or self.width
        h = height or self.height

        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError:
            logger.warning(
                "Playwright not installed. Skipping PNG render for %s. "
                "Install with: pip install playwright && playwright install chromium",
                html_path.name,
            )
            return png_path  # Return path even if file doesn't exist

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto(html_path.as_uri(), wait_until="networkidle")
                page.wait_for_timeout(wait_ms)
                page.screenshot(path=str(png_path), full_page=False)
                browser.close()
            logger.info("Rendered PNG: %s", png_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Playwright rendering failed for %s: %s", html_path.name, exc)
            raise

        return png_path

    def render_all_to_png(
        self,
        html_paths: dict[str, Path],
        output_dir: Optional[str | Path] = None,
    ) -> dict[str, Path]:
        """
        Batch render all HTML diagrams to PNG.

        Returns
        -------
        dict
            Mapping of diagram_id → Path to PNG.
        """
        out_dir = Path(output_dir) if output_dir else self.output_dir
        results: dict[str, Path] = {}
        for diagram_id, html_path in html_paths.items():
            png_path = out_dir / f"{diagram_id}.png"
            try:
                self.render_to_png(html_path, png_path)
                results[diagram_id] = png_path
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to render '%s': %s", diagram_id, exc)
        return results

    # ------------------------------------------------------------------
    # PNG rendering via mermaid.ink API (zero-dependency)
    # ------------------------------------------------------------------

    def render_to_png_via_api(
        self,
        mermaid_code: str,
        output_path: str | Path,
        retries: int = 2,
        rate_limit: float = 0.3,
    ) -> Path:
        """
        Render Mermaid code to PNG via the mermaid.ink public API.

        This requires no local dependencies — it sends the diagram as a
        base64url-encoded URL and downloads the resulting PNG.

        Parameters
        ----------
        mermaid_code : str
            Raw Mermaid diagram definition.
        output_path : str | Path
            Where to save the PNG.
        retries : int
            Number of retry attempts on failure.
        rate_limit : float
            Seconds to wait between API calls (to avoid throttling).

        Returns
        -------
        Path
            Path to the rendered PNG file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        encoded = base64.urlsafe_b64encode(
            mermaid_code.strip().encode("utf-8")
        ).decode("ascii")
        bg_hex = self.bg_color.lstrip("#")
        url = (
            f"https://mermaid.ink/img/{encoded}"
            f"?type=png&theme={self.theme}&bgColor=!{bg_hex}"
        )

        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Narractive/2.0"}
                )
                resp = urllib.request.urlopen(req, timeout=30)
                data = resp.read()

                if len(data) < 100 or data[:4] != b"\x89PNG":
                    logger.warning(
                        "mermaid.ink: response not a valid PNG (%d bytes)", len(data),
                    )
                    if attempt < retries:
                        time.sleep(1)
                        continue
                    raise RuntimeError("mermaid.ink returned invalid PNG data")

                output_path.write_bytes(data)
                logger.info(
                    "mermaid.ink rendered: %s (%s bytes)",
                    output_path.name, f"{len(data):,}",
                )
                if rate_limit > 0:
                    time.sleep(rate_limit)
                return output_path

            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                if attempt < retries:
                    logger.debug("mermaid.ink attempt %d failed: %s", attempt + 1, exc)
                    time.sleep(1)
                    continue
                raise RuntimeError(f"mermaid.ink API error after {retries + 1} attempts: {exc}")

        raise RuntimeError("mermaid.ink: exhausted retries")

    # ------------------------------------------------------------------
    # PNG rendering via mmdc (mermaid-cli)
    # ------------------------------------------------------------------

    def render_to_png_via_mmdc(
        self,
        mmd_path: str | Path,
        output_path: str | Path,
    ) -> Path:
        """
        Render an ``.mmd`` file to PNG using the local ``mmdc`` CLI.

        Parameters
        ----------
        mmd_path : str | Path
            Path to the Mermaid source file.
        output_path : str | Path
            Where to save the PNG.

        Returns
        -------
        Path
            Path to the rendered PNG file.
        """
        mmd_path = Path(mmd_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write a temporary config for dark theme
        config_data = {
            "theme": self.theme,
            "themeVariables": {
                "darkMode": True,
                "background": self.bg_color,
                "primaryColor": "#3498db",
                "primaryTextColor": "#ecf0f1",
                "primaryBorderColor": "#2980b9",
                "lineColor": "#bdc3c7",
                "secondaryColor": "#2ecc71",
                "tertiaryColor": "#9b59b6",
                "fontFamily": f"{self.font_family}, sans-serif",
                "fontSize": "16px",
            },
        }
        config_fd, config_path = tempfile.mkstemp(suffix=".json", prefix="mermaid_cfg_")
        try:
            with os.fdopen(config_fd, "w") as f:
                json.dump(config_data, f)

            cmd = [
                "mmdc",
                "-i", str(mmd_path),
                "-o", str(output_path),
                "-w", str(self.width),
                "-H", str(self.height),
                "-b", self.bg_color,
                "-c", config_path,
                "--scale", "2",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise RuntimeError(f"mmdc failed: {result.stderr.strip()[:300]}")

            logger.info("mmdc rendered: %s", output_path.name)
            return output_path
        finally:
            Path(config_path).unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Auto-detect backend
    # ------------------------------------------------------------------

    def detect_backend(self) -> str:
        """
        Auto-detect the best available rendering backend.

        Returns
        -------
        str
            One of ``"playwright"``, ``"mmdc"``, or ``"api"``.
        """
        # Check Playwright
        try:
            from playwright.sync_api import sync_playwright  # type: ignore  # noqa: F401
            return "playwright"
        except ImportError:
            pass

        # Check mmdc
        try:
            result = subprocess.run(
                ["mmdc", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return "mmdc"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback to API
        return "api"

    def render_to_png_auto(
        self,
        mermaid_code: str,
        output_path: str | Path,
        backend: Optional[str] = None,
    ) -> Path:
        """
        Render Mermaid code to PNG using the best available backend.

        Parameters
        ----------
        mermaid_code : str
            Raw Mermaid diagram definition.
        output_path : str | Path
            Where to save the PNG.
        backend : str, optional
            Force a specific backend (``"playwright"``, ``"mmdc"``, ``"api"``).
            If None, auto-detects.

        Returns
        -------
        Path
            Path to the rendered PNG file.
        """
        output_path = Path(output_path)
        selected = backend or self.detect_backend()
        logger.debug("Using rendering backend: %s", selected)

        if selected == "playwright":
            # Generate HTML first, then render via Playwright
            html_path = output_path.with_suffix(".html")
            self.generate_diagram(mermaid_code, html_path)
            return self.render_to_png(html_path, output_path)
        elif selected == "mmdc":
            mmd_path = output_path.with_suffix(".mmd")
            self.write_mmd(mermaid_code, mmd_path)
            return self.render_to_png_via_mmdc(mmd_path, output_path)
        else:  # "api"
            return self.render_to_png_via_api(mermaid_code, output_path)

    # ------------------------------------------------------------------
    # Mermaid source file writer
    # ------------------------------------------------------------------

    def write_mmd(self, mermaid_code: str, output_path: str | Path) -> Path:
        """
        Write Mermaid source code to an ``.mmd`` file.

        Parameters
        ----------
        mermaid_code : str
            Raw Mermaid diagram definition.
        output_path : str | Path
            Where to save the ``.mmd`` file.

        Returns
        -------
        Path
            Path to the written file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(mermaid_code.strip() + "\n", encoding="utf-8")
        logger.debug("Wrote .mmd source: %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # HTML builder
    # ------------------------------------------------------------------

    def _build_html(self, mermaid_code: str, title: str) -> str:
        """Build a complete styled HTML page for the diagram."""
        # Try loading the external template first
        if _TEMPLATE_PATH.exists():
            template = _TEMPLATE_PATH.read_text(encoding="utf-8")
            return (
                template
                .replace("{{TITLE}}", title)
                .replace("{{SUBTITLE}}", self.subtitle)
                .replace("{{FOOTER_URL}}", self.footer_url)
                .replace("{{MERMAID_CODE}}", mermaid_code)
                .replace("{{BG_COLOR}}", self.bg_color)
                .replace("{{FONT_FAMILY}}", self.font_family)
                .replace("{{THEME}}", self.theme)
            )
        # Inline fallback template
        return _INLINE_TEMPLATE.format(
            title=title,
            subtitle=self.subtitle,
            footer_url=self.footer_url,
            mermaid_code=mermaid_code,
            bg_color=self.bg_color,
            font_family=self.font_family,
            theme=self.theme,
        )


# ---------------------------------------------------------------------------
# Inline fallback template (used when diagrams/template.html is absent)
# ---------------------------------------------------------------------------
_INLINE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920" />
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: linear-gradient(135deg, {bg_color} 0%, #16213e 60%, #0f3460 100%);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    font-family: '{font_family}', 'Segoe UI', sans-serif;
    color: #e0e0e0;
    overflow: hidden;
  }}
  .slide-container {{
    width: 1920px;
    height: 1080px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    padding: 40px;
  }}
  .title-bar {{
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    background: rgba(76, 175, 80, 0.15);
    border-bottom: 2px solid #4CAF50;
    padding: 16px 40px;
    display: flex;
    align-items: center;
    gap: 16px;
  }}
  .logo {{
    width: 36px;
    height: 36px;
    background: #4CAF50;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: bold;
    color: #fff;
  }}
  .title-text {{
    font-size: 28px;
    font-weight: 600;
    color: #fff;
    letter-spacing: 0.5px;
  }}
  .subtitle {{
    font-size: 16px;
    color: #4CAF50;
    margin-left: auto;
    font-style: italic;
  }}
  .diagram-wrapper {{
    margin-top: 80px;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    animation: fadeIn 0.8s ease-in;
  }}
  .mermaid {{
    transform-origin: center;
  }}
  .footer {{
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(0,0,0,0.3);
    padding: 10px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 13px;
    color: rgba(255,255,255,0.5);
    border-top: 1px solid rgba(76,175,80,0.2);
  }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(20px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
</style>
</head>
<body>
<div class="slide-container">
  <div class="title-bar">
    <div class="logo">F</div>
    <div class="title-text">{title}</div>
    <div class="subtitle">{subtitle}</div>
  </div>
  <div class="diagram-wrapper">
    <div class="mermaid">
{mermaid_code}
    </div>
  </div>
  <div class="footer">
    <span>{title}</span>
    <span>{footer_url}</span>
  </div>
</div>
<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: '{theme}',
    themeVariables: {{
      primaryColor: '#1976D2',
      primaryTextColor: '#ffffff',
      primaryBorderColor: '#4CAF50',
      lineColor: '#4CAF50',
      secondaryColor: '#16213e',
      tertiaryColor: '#0f3460',
      background: '{bg_color}',
      mainBkg: '#16213e',
      nodeBorder: '#4CAF50',
      clusterBkg: 'rgba(76,175,80,0.1)',
      titleColor: '#ffffff',
      edgeLabelBackground: '#16213e',
      fontSize: '18px',
    }},
    flowchart: {{ curve: 'basis', padding: 20 }},
    sequence: {{ actorMargin: 80, mirrorActors: false }},
    fontFamily: '{font_family}, Segoe UI, sans-serif',
  }});
</script>
</body>
</html>
"""
