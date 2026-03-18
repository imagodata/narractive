"""
V01 Sequence 5 — CONFIGURATION & DEBUG
========================================
- Changement de langue (22 langues)
- Mode verbose (FEEDBACK_LEVEL)
- Panneau de logs

Uses TimelineSequence for narration-synchronized execution.
"""
from __future__ import annotations

import pyautogui

from video_automation.core.timeline import NarrationCue
from video_automation.sequences.base import TimelineSequence


class V01S05ConfigDebug(TimelineSequence):
    name = "V01 — Configuration & Debug"
    sequence_id = "v01_s05"
    duration_estimate = 45.0
    obs_scene = "App + FilterMate"
    diagram_ids = ["v01_languages", "v01_feedback_levels"]
    narration_text = ""  # Narration is now in the cues

    def build_timeline(self, obs, app, config):
        regions = config["app"]["regions"]
        move_dur = config["timing"].get("mouse_move_duration", 0.5)

        def change_language_to_en():
            app.open_filtermate_config()
            app.wait(1.0)
            self.edit_config_value(app, config, "about_config_language_field", "en")
            app.close_dialog()
            app.wait(0.5)

        def show_english_interface():
            app.focus_panel()
            app.wait(1.5)

        def restore_language_to_fr():
            app.open_filtermate_config()
            app.wait(1.0)
            self.edit_config_value(app, config, "about_config_language_field", "fr")
            app.close_dialog()
            app.wait(0.5)

        def change_feedback_to_verbose():
            app.open_filtermate_config()
            app.wait(1.0)
            self.edit_config_value(
                app, config, "about_config_feedback_level_field", "verbose"
            )
            app.close_dialog()
            app.wait(0.5)

        def trigger_filter_verbose():
            app.select_tab("FILTERING")
            app.wait(0.5)
            app.click_action_button("filter")
            app.wait(2.5)

        def open_log_panel():
            app.focus_app()
            app.wait(0.5)
            app.open_log_messages_panel()
            app.wait(1.5)
            log_tab = regions.get("log_panel_filtermate_tab")
            if log_tab:
                pyautogui.click(log_tab["x"], log_tab["y"], duration=move_dur)
            app.wait(2.0)

        def trigger_filter_and_show_log():
            app.select_tab("FILTERING")
            app.wait(0.3)
            app.click_action_button("filter")
            app.wait(2.0)
            # Show new entries in log
            log_tab = regions.get("log_panel_filtermate_tab")
            if log_tab:
                pyautogui.click(log_tab["x"], log_tab["y"], duration=move_dur)
            app.wait(1.5)

        return [
            # --- LANGUAGE ---
            # Cue 0: Intro language
            NarrationCue(
                label="Intro langues",
                text=(
                    "FilterMate parle 22 langues. Français, anglais, espagnol, "
                    "allemand, chinois, japonais, arabe..."
                ),
                sync="during",
                actions=lambda: app.focus_panel(),
                post_delay=0.3,
            ),
            # Cue 1: Change language
            NarrationCue(
                label="Changement langue EN",
                text=(
                    "La langue se change dans la configuration. "
                    "Changeons vers l'anglais..."
                ),
                sync="during",
                actions=lambda: change_language_to_en(),
                post_delay=0.3,
            ),
            # Cue 2: Show result
            NarrationCue(
                label="Interface mise à jour",
                text=(
                    "Toute l'interface se met à jour immédiatement, "
                    "sans relancer le plugin."
                ),
                sync="during",
                actions=lambda: show_english_interface(),
                post_delay=0.3,
            ),
            # Cue 3: Language diagram
            NarrationCue(
                label="Diagramme langues",
                text="",
                actions=lambda: self.show_diagram(
                    obs, "v01_languages", duration=4.0
                ),
                post_delay=0.3,
            ),
            # Cue 4: Restore French
            NarrationCue(
                label="Retour au français",
                text="Repassons en français pour la suite.",
                sync="during",
                actions=lambda: restore_language_to_fr(),
                post_delay=0.3,
            ),
            # --- VERBOSE MODE ---
            # Cue 5: Intro verbose
            NarrationCue(
                label="Intro mode verbose",
                text=(
                    "Astuce pour les débutants : activez le mode verbose. "
                    "Dans la configuration, changez FEEDBACK_LEVEL de normal à verbose."
                ),
                sync="during",
                actions=lambda: change_feedback_to_verbose(),
                post_delay=0.3,
            ),
            # Cue 6: Show verbose messages
            NarrationCue(
                label="Démo verbose",
                text=(
                    "En mode verbose, FilterMate vous explique tout ce qu'il fait. "
                    "Trois niveaux : minimal pour les erreurs, "
                    "normal pour un retour équilibré, et verbose pour tout voir."
                ),
                sync="during",
                actions=lambda: trigger_filter_verbose(),
                post_delay=0.3,
            ),
            # Cue 7: Verbose diagram
            NarrationCue(
                label="Diagramme feedback levels",
                text="",
                actions=lambda: self.show_diagram(
                    obs, "v01_feedback_levels", duration=4.0
                ),
                post_delay=0.3,
            ),
            # --- LOG PANEL ---
            # Cue 8: Open log panel
            NarrationCue(
                label="Panneau de logs",
                text=(
                    "En complément, FilterMate écrit ses logs dans le panneau standard. "
                    "Allez dans Vue, Panneaux, Messages de log. "
                    "Vous trouverez un onglet dédié FilterMate."
                ),
                scene=config["obs"]["scenes"].get("app_fullscreen", "App Fullscreen"),
                sync="during",
                actions=lambda: open_log_panel(),
                post_delay=0.3,
            ),
            # Cue 9: Show log entries
            NarrationCue(
                label="Entrées de log",
                text=(
                    "C'est ici que vous pouvez suivre les requêtes SQL générées, "
                    "les temps d'exécution, les erreurs éventuelles."
                ),
                sync="during",
                actions=lambda: trigger_filter_and_show_log(),
                post_delay=0.5,
            ),
        ]
