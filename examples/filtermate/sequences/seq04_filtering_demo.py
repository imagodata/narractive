"""
Sequence 04 -- FILTRAGE VECTEUR DEMO (2:00) -- The Big One
=========================================================
Visuel: Demo en direct -- PostGIS routes + batiments -> filtre en temps reel.

Steps:
  1.  Focus QGIS, confirm PostGIS layers are loaded
  2.  Click on FilterMate panel
  3.  Select source layer: routes (1M entites)
  4.  Select target layer: batiments via Layers to Filter toggle
  5.  Enable Geometric Predicates -> select "touches"
  6.  Enable Buffer Value -> set 50 (metres)
  7.  Click Filter button -> wait for result
  8.  Show filtered result on map (pan / zoom around)
  9.  Click Undo -> show previous state
  10. Show Favorites -> apply a saved favorite filter
  11. Show result

Diagrams shown: 04_workflow, 05_predicates

If FilterMate >= 5.0 is available, filtering steps use the
:class:`~narractive.core.filtermate_adapter.FilterMateAdapter` for
deterministic, signal-driven control. Otherwise falls back to
PyAutoGUI-based GUI automation.
"""

from __future__ import annotations

import logging
import time

from narractive.sequences.base import VideoSequence

logger = logging.getLogger(__name__)


def _try_filtermate_adapter():
    """Attempt to instantiate and connect a FilterMateAdapter.

    Returns
    -------
    FilterMateAdapter or None
        Connected adapter, or None if unavailable.
    """
    try:
        from narractive.core.filtermate_adapter import FilterMateAdapter

        adapter = FilterMateAdapter()
        if adapter.connect():
            return adapter
    except Exception:  # noqa: BLE001
        pass
    return None


class Seq04FilteringDemo(VideoSequence):
    name = "Filtrage Vecteur — Demo Live"
    sequence_id = "seq04"
    duration_estimate = 120.0
    obs_scene = "App + Panel"
    diagram_ids = ["04_workflow", "05_predicates"]
    narration_text = (
        "Voila un jeu de donnees BDTopo -- 1 million de batiments dans PostgreSQL. "
        "Je selectionne ma couche source : les routes. "
        "Ma couche cible : les batiments. "
        "Je choisis le predicat geometrique touches, "
        "j'ajoute un buffer de 50 metres... et j'applique. "
        "FilterMate detecte automatiquement que c'est une couche PostgreSQL, "
        "cree une vue materialisee optimisee et renvoie le resultat : "
        "1 milliseconde. Exactement. "
        "Je peux annuler avec l'undo -- 100 etats conserves. "
        "Ou rappeler un filtre favori enregistre precedemment. "
        "Tout ca sans jamais ecrire une seule ligne de SQL."
    )

    def execute(self, obs, app, config):
        timing = config.get("timing", {})
        action_pause = timing.get("action_pause", 1.0)

        # Try to use FilterMateAdapter for deterministic filtering
        fm = _try_filtermate_adapter()
        if fm is not None:
            logger.info("Using FilterMateAdapter for filtering steps")
        else:
            logger.info(
                "FilterMateAdapter not available — falling back to GUI automation"
            )

        # -- PART 1: Setup and layer selection ---------------------------------

        # 1. Focus QGIS -- show the loaded project with PostGIS layers
        app.focus_app()
        app.wait(1.5)

        # Slowly pan the mouse over the Layers panel to show loaded layers
        regions = config.get("app", {}).get("regions", {})
        canvas = regions.get("main_canvas", {})
        if canvas:
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

        # -- PART 2: Configure and apply filter --------------------------------

        # 5. Enable geometric predicates -> select "touches"
        self._log.info("Step 5: Selecting predicate 'touches'")
        app.select_predicate("touches")
        app.wait(action_pause)

        # Show the predicates diagram briefly
        self.show_diagram(obs, "05_predicates", duration=4.0)

        # 6. Enable buffer -> set 50m
        self._log.info("Step 6: Setting buffer to 50m")
        app.set_buffer_value(50, unit="m")
        app.wait(action_pause)

        # 7. Apply filter -- the key moment!
        self._log.info("Step 7: Applying filter")
        obs.switch_scene(obs.scenes.get("app_with_panel", "App + Panel"))

        if fm is not None:
            # Use FilterMateAdapter for deterministic, signal-driven filtering
            success = fm.apply_filter(
                "batiments",
                "intersects($geometry, geometry(get_feature('routes', 'id', @current_feature_id)))",
            )
            if not success:
                logger.warning(
                    "FilterMateAdapter.apply_filter failed — "
                    "falling back to GUI click"
                )
                app.click_action_button("filter")
                time.sleep(3.0)
        else:
            # Fallback: GUI automation
            app.click_action_button("filter")
            time.sleep(3.0)

        # 8. Show filtered result -- pan around the canvas
        self._log.info("Step 8: Showing filtered result on map")
        if canvas:
            app.move_mouse_to(cx, cy, duration=1.0)
        app.wait(2.0)

        # Show the workflow diagram
        self.show_diagram(obs, "04_workflow", duration=5.0)

        # -- PART 3: Undo and Favorites ----------------------------------------

        # 9. Click Undo -- show previous state
        self._log.info("Step 9: Clicking UNDO")
        app.focus_panel()

        if fm is not None:
            # Clear the filter via the adapter (equivalent to undo)
            fm.clear_filter("batiments")
        else:
            app.click_action_button("undo")
        app.wait(action_pause)

        # 10. Show Favorites -- apply a saved favorite
        self._log.info("Step 10: Opening Favorites")
        app.click_action_button("favorites")
        app.wait(1.0)

        # Navigate to first saved favorite
        import pyautogui  # type: ignore

        pyautogui.press("down")
        app.wait(0.3)
        pyautogui.press("return")
        app.wait(2.0)

        # 11. Show result
        self._log.info("Step 11: Showing final result")
        if canvas:
            app.move_mouse_to(cx, cy, duration=1.0)
        app.wait(2.0)

        # Cleanup: disconnect adapter if we used it
        if fm is not None:
            active = fm.get_active_filters()
            if active:
                logger.info("Active filters at end: %s", active)
            fm.disconnect()

        self._log.info("Filtering demo complete!")
