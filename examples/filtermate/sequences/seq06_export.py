"""
Séquence 6 — EXPORT GEOPACKAGE (1:00)
========================================
Visuel: Onglet Export — sélectionner couches, options, Export → GPKG.
Diagramme 7 (Export GeoPackage) affiché.
"""

from __future__ import annotations

from narractive.sequences.base import VideoSequence


class Seq06Export(VideoSequence):
    name = "Export GeoPackage"
    sequence_id = "seq06"
    duration_estimate = 60.0
    obs_scene = "App + Panel"
    diagram_ids = ["07_export"]
    narration_text = (
        "L'export GeoPackage est l'une des fonctionnalités les plus puissantes. "
        "FilterMate ne se contente pas d'exporter vos données — "
        "il embarque votre projet QGIS complet dans le fichier. "
        "Hiérarchie des groupes, styles des couches, système de coordonnées — tout est préservé. "
        "À l'ouverture, QGIS reconstitue automatiquement votre arborescence. "
        "Idéal pour partager un livrable complet en un seul fichier."
    )

    def execute(self, obs, app, config):
        import pyautogui  # type: ignore

        app.focus_app()
        app.focus_panel()

        # 1. Switch to EXPORTING tab
        app.select_tab("EXPORTING")
        app.wait(1.5)

        # 2. Highlight the export options panel
        #    Move mouse to show available options (layers, CRS, output path, etc.)
        regions = config.get("app", {}).get("regions", {})
        dock = regions.get("filtermate_dock", {})
        if dock:
            app.highlight_area("filtermate_dock", duration=2.0)

        # 3. Simulate selecting all layers for export (check "All layers" checkbox if visible)
        app.click_button("btn_select_all_layers", confidence=0.75)
        app.wait(0.5)

        # 4. Scroll down to show export options (output path, CRS, etc.)
        app.scroll_down(clicks=2)
        app.wait(0.8)
        app.scroll_up(clicks=2)
        app.wait(0.5)

        # 5. Click Export button (but don't actually confirm to keep demo clean)
        #    For the demo we just move to the button
        app.click_button("btn_export_gpkg", confidence=0.75)
        app.wait(1.0)
        pyautogui.press("escape")  # Cancel the file dialog
        app.wait(0.5)

        # 6. Show the export diagram
        self.show_diagram(obs, "07_export", duration=10.0)

        # 7. Return to FILTERING tab for clean handoff
        app.select_tab("FILTERING")
        app.wait(1.0)
