"""
Séquence 9 — FONCTIONNALITÉS AVANCÉES (0:45)
=============================================
Visuel: Montage — undo/redo, favoris, filtre chaîné, métriques.
Diagrammes 11 (Undo/Redo) et 12 (Métriques Qualité).
"""

from __future__ import annotations

from narractive.sequences.base import VideoSequence


class Seq09Advanced(VideoSequence):
    name = "Fonctionnalités Avancées"
    sequence_id = "seq09"
    duration_estimate = 45.0
    obs_scene = "App + Panel"
    diagram_ids = ["11_undo_redo", "12_metrics"]
    narration_text = (
        "FilterMate va plus loin : filtrage chaîné avec buffers dynamiques, "
        "détection automatique de la clé primaire PostgreSQL "
        "pour les tables BDTopo et OSM, "
        "100 états undo/redo, et un système de favoris avec contexte spatial. "
        "396 tests automatisés. 22 langues. Compatible QGIS 3 et 4."
    )

    def execute(self, obs, app, config):
        import pyautogui  # type: ignore

        app.focus_app()
        app.focus_panel()
        app.select_tab("FILTERING")
        app.wait(1.0)

        # 1. Demonstrate Undo/Redo stack
        self._log.info("Demonstrating Undo/Redo")
        for _ in range(3):
            app.click_action_button("undo")
            app.wait(0.6)
        for _ in range(3):
            app.click_action_button("redo")
            app.wait(0.6)

        # 2. Show Undo/Redo state diagram
        self.show_diagram(obs, "11_undo_redo", duration=8.0)

        # 3. Demonstrate Favorites
        self._log.info("Demonstrating Favorites")
        app.focus_panel()
        app.click_action_button("favorites")
        app.wait(1.0)
        pyautogui.press("down")
        pyautogui.press("return")
        app.wait(1.5)

        # 4. Show quality metrics diagram
        self.show_diagram(obs, "12_metrics", duration=8.0)

        app.focus_app()
        app.wait(1.0)
