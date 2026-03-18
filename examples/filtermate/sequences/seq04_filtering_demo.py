"""
Séquence 4 — FILTRAGE VECTEUR DEMO (2:00) ← The Big One
=========================================================
Visuel: Demo en direct — PostGIS routes + bâtiments → filtre en temps réel.

Steps:
  1.  Focus QGIS, confirm PostGIS layers are loaded
  2.  Click on FilterMate panel
  3.  Select source layer: routes (1M entités)
  4.  Select target layer: batiments via Layers to Filter toggle
  5.  Enable Geometric Predicates → select "touches"
  6.  Enable Buffer Value → set 50 (metres)
  7.  Click Filter button → wait for result
  8.  Show filtered result on map (pan / zoom around)
  9.  Click Undo → show previous state
  10. Show Favorites → apply a saved favorite filter
  11. Show result

Diagrams shown: 04_workflow, 05_predicates
"""

from __future__ import annotations

import time

from video_automation.sequences.base import VideoSequence


class Seq04FilteringDemo(VideoSequence):
    name = "Filtrage Vecteur — Demo Live"
    sequence_id = "seq04"
    duration_estimate = 120.0
    obs_scene = "App + Panel"
    diagram_ids = ["04_workflow", "05_predicates"]
    narration_text = (
        "Voilà un jeu de données BDTopo — 1 million de bâtiments dans PostgreSQL. "
        "Je sélectionne ma couche source : les routes. "
        "Ma couche cible : les bâtiments. "
        "Je choisis le prédicat géométrique touches, "
        "j'ajoute un buffer de 50 mètres... et j'applique. "
        "FilterMate détecte automatiquement que c'est une couche PostgreSQL, "
        "crée une vue matérialisée optimisée et renvoie le résultat : "
        "1 milliseconde. Exactement. "
        "Je peux annuler avec l'undo — 100 états conservés. "
        "Ou rappeler un filtre favori enregistré précédemment. "
        "Tout ça sans jamais écrire une seule ligne de SQL."
    )

    def execute(self, obs, app, config):
        timing = config.get("timing", {})
        action_pause = timing.get("action_pause", 1.0)

        # ── PART 1: Setup and layer selection ──────────────────────────────────

        # 1. Focus QGIS — show the loaded project with PostGIS layers
        app.focus_app()
        app.wait(1.5)

        # Slowly pan the mouse over the Layers panel to show loaded layers
        regions = config.get("app", {}).get("regions", {})
        canvas = regions.get("main_canvas", {})
        if canvas:
            # Simulate exploring the map
            cx = canvas.get("x", 960) + canvas.get("width", 800) // 2
            cy = canvas.get("y", 400) + canvas.get("height", 600) // 2
            app.move_mouse_to(cx - 300, cy - 150, duration=1.5)
            app.wait(0.8)
            app.move_mouse_to(cx + 300, cy + 150, duration=1.5)
            app.wait(0.8)

        # 2. Click on FilterMate panel
        app.focus_panel()
        app.select_tab("FILTERING")
        app.wait(action_pause)

        # 3. Select source layer: routes
        self._log.info("Step 3: Selecting source layer 'routes'")
        app.select_layer("routes")
        app.wait(action_pause)

        # 4. Select target layer: batiments via toggle
        self._log.info("Step 4: Selecting target layer 'batiments'")
        app.select_target_layer("batiments")
        app.wait(action_pause)

        # ── PART 2: Configure and apply filter ─────────────────────────────────

        # 5. Enable geometric predicates → select "touches"
        self._log.info("Step 5: Selecting predicate 'touches'")
        app.select_predicate("touches")
        app.wait(action_pause)

        # Show the predicates diagram briefly
        self.show_diagram(obs, "05_predicates", duration=4.0)

        # 6. Enable buffer → set 50m
        self._log.info("Step 6: Setting buffer to 50m")
        app.set_buffer_value(50, unit="m")
        app.wait(action_pause)

        # 7. Click Filter button — the key moment!
        self._log.info("Step 7: Clicking FILTER button (the money shot)")
        obs.switch_scene(obs.scenes.get("app_with_panel", "App + Panel"))
        app.click_action_button("filter")

        # Wait for query to complete (PostGIS may take 0.5–3s depending on hardware)
        self._log.info("Waiting for filter result…")
        time.sleep(3.0)

        # 8. Show filtered result — pan around the canvas to show result
        self._log.info("Step 8: Showing filtered result on map")
        if canvas:
            app.move_mouse_to(cx, cy, duration=1.0)
        app.wait(2.0)

        # Show the workflow diagram
        self.show_diagram(obs, "04_workflow", duration=5.0)

        # ── PART 3: Undo and Favorites ─────────────────────────────────────────

        # 9. Click Undo — show previous state
        self._log.info("Step 9: Clicking UNDO")
        app.focus_panel()
        app.click_action_button("undo")
        app.wait(action_pause)

        # 10. Show Favorites — click the favorites button
        self._log.info("Step 10: Opening Favorites")
        app.click_action_button("favorites")
        app.wait(1.0)

        # Navigate to a saved favorite (first entry in the list)
        import pyautogui  # type: ignore
        pyautogui.press("down")    # Select first favorite
        app.wait(0.3)
        pyautogui.press("return")  # Apply it
        app.wait(2.0)

        # 11. Show result
        self._log.info("Step 11: Showing final result")
        if canvas:
            app.move_mouse_to(cx, cy, duration=1.0)
        app.wait(2.0)

        self._log.info("Filtering demo complete!")
