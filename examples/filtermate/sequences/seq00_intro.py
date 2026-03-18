"""
Séquence 0 — INTRO + HOOK (0:20)
=================================
Visuel: Écran avec carte complexe, 10+ layers chargés.
Hook : frustration → FilterMate s'ouvre → filtre en 1 clic.
"""

from __future__ import annotations

from video_automation.sequences.base import VideoSequence


class Seq00Intro(VideoSequence):
    name = "Intro + Hook"
    sequence_id = "seq00"
    duration_estimate = 20.0
    obs_scene = "Intro"
    diagram_ids = []
    narration_text = (
        "Vous avez 1 million de bâtiments dans votre PostGIS ? "
        "Vous cherchez juste ceux à 200 mètres d'une route spécifique ? "
        "Et vous voulez ça en moins de 2 secondes ? "
        "C'est exactement ce que fait FilterMate."
    )

    def setup(self, obs, app, config):
        # Switch to the dedicated Intro scene (animated logo / title card)
        obs.transition_to_intro()
        app.wait(2.0)

    def execute(self, obs, app, config):
        """
        Play the intro slide for the configured duration, then
        transition to QGIS to tease the interface.
        """
        # 1. Intro title card plays for ~10s (narration fills the time)
        app.wait(10.0)

        # 2. Cut to QGIS Fullscreen — show a loaded project with many layers
        obs.switch_scene(obs.scenes.get("app_fullscreen", "App Fullscreen"))
        app.focus_app()
        app.wait(2.0)

        # 3. Pan mouse around the layer panel to show complexity
        regions = config.get("app", {}).get("regions", {})
        canvas = regions.get("main_canvas", {})
        if canvas:
            cx = canvas.get("x", 960)
            cy = canvas.get("y", 400)
            # Slow pan across the map
            app.move_mouse_to(cx - 200, cy - 100, duration=1.5)
            app.wait(1.0)
            app.move_mouse_to(cx + 200, cy + 100, duration=1.5)
            app.wait(1.0)

        # 4. Switch to QGIS + FilterMate scene — the dock is now visible
        obs.switch_scene(obs.scenes.get("app_with_panel", "App + Panel"))
        app.focus_panel()
        app.wait(2.0)

    def teardown(self, obs, app, config):
        # Return to main scene
        obs.transition_to_main()
        super().teardown(obs, app, config)
