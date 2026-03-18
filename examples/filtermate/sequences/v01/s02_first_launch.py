"""
V01 Sequence 2 — PREMIER LANCEMENT + DÉCOUVERTE INTERFACE
===========================================================
Ouvrir FilterMate (dock vide), découvrir les 3 zones de l'interface
(Exploring, Toolbox, Header) avec cycle des onglets,
puis sélectionner la couche source, changer le champ d'affichage,
naviguer avec next/prev et montrer la détection automatique (diagramme).

Uses TimelineSequence for narration-synchronized execution.
"""
from __future__ import annotations

import pyautogui

from video_automation.core.timeline import NarrationCue
from video_automation.sequences.base import TimelineSequence


class V01S02FirstLaunch(TimelineSequence):
    name = "V01 — Premier lancement"
    sequence_id = "v01_s02"
    duration_estimate = 95.0
    obs_scene = "App + Panel"
    diagram_ids = ["v01_interface_zones", "v01_display_field_detection"]
    narration_text = ""  # Narration is now in the cues

    def build_timeline(self, obs, app, config):
        regions = config["app"]["regions"]
        move_dur = config["timing"].get("mouse_move_duration", 0.5)

        def show_tabs_cycle():
            """Cycle through toolbox tabs without hovering individual buttons."""
            app.highlight_area("toolbox_zone", duration=2.5)
            # FILTERING
            app.select_tab("FILTERING")
            app.wait(0.8)
            # EXPORTING
            app.select_tab("EXPORTING")
            app.wait(0.8)
            # CONFIGURATION
            app.select_tab("CONFIGURATION")
            app.wait(0.8)
            # Retour FILTERING
            app.select_tab("FILTERING")

        def click_prev_then_next():
            """Click prev to go to previous department, then next to return."""
            btn_prev = regions.get("exploring_feature_prev_btn")
            btn_next = regions.get("exploring_feature_next_btn")
            if btn_prev:
                pyautogui.click(btn_prev["x"], btn_prev["y"], duration=move_dur)
            app.wait(1.5)
            if btn_next:
                pyautogui.click(btn_next["x"], btn_next["y"], duration=move_dur)
            app.wait(1.0)

        def activate_auto_current_layer():
            """Enable auto-sync between layer tree and source layer combo."""
            self._log.info("Activating auto current layer sync")
            app.click_at("btn_auto_current_layer")
            app.wait(0.5)

        def click_layer_communes():
            """Click communes in QGIS layer panel to switch source layer."""
            self._log.info("Clicking communes in layer panel")
            app.click_at("layer_panel_name_communes")
            app.wait(1.0)

        def click_layer_departements():
            """Click departements in QGIS layer panel to switch back."""
            self._log.info("Clicking departements in layer panel")
            app.click_at("layer_panel_name_departements")
            app.wait(1.0)

        return [
            # Cue 0: Open FilterMate — dock is empty
            NarrationCue(
                label="Lancement FilterMate",
                text=(
                    "Pour lancer FilterMate, cliquez sur son icône "
                    "dans la barre d'outils, "
                    "ou allez dans le menu Extensions puis FilterMate."
                ),
                sync="during",
                actions=lambda: (
                    app.focus_app(),
                    app.open_filtermate_toolbar(),
                ),
                post_delay=0.5,
            ),
            # ── DÉCOUVERTE INTERFACE : LES 3 ZONES ─────────────

            # Cue 1: Introduction interface
            NarrationCue(
                label="Introduction interface",
                text=(
                    "Prenons un moment pour comprendre l'interface. "
                    "Elle est divisée en 3 zones principales, "
                    "séparées par un splitter vertical."
                ),
                sync="during",
                actions=lambda: app.focus_panel(),
                post_delay=0.5,
            ),
            # Cue 2: Zone A — Exploring Zone
            NarrationCue(
                label="Zone d'Exploration",
                text=(
                    "En haut, la Zone d'Exploration. "
                    "C'est ici que vous parcourez et sélectionnez "
                    "les entités de vos couches."
                ),
                sync="during",
                actions=lambda: app.highlight_area("exploring_zone", duration=3.0),
                post_delay=0.3,
            ),
            # Cue 3: Zone B — Toolbox + cycle des onglets
            NarrationCue(
                label="Toolbox + onglets",
                text=(
                    "En bas, la Toolbox. "
                    "Trois onglets : FILTERING, EXPORTING et CONFIGURATION."
                ),
                sync="during",
                actions=lambda: show_tabs_cycle(),
                post_delay=0.3,
            ),
            # Cue 4: Header — badges
            NarrationCue(
                label="Header badges",
                text=(
                    "Remarquez aussi le header : "
                    "la pastille orange indique vos favoris, "
                    "et la pastille bleue affiche le backend actif."
                ),
                sync="during",
                actions=lambda: (
                    app.hover_region("badge_favorites", duration=1.5),
                    app.hover_region("badge_backend", duration=1.5),
                ),
                post_delay=0.3,
            ),
            # Cue 5: Diagram — 3 zones
            NarrationCue(
                label="Diagramme zones",
                text="",
                actions=lambda: self.show_diagram_and_return(
                    obs, app, "v01_interface_zones", duration=5.0
                ),
                post_delay=0.5,
            ),

            # ── SÉLECTION COUCHE SOURCE ────────────────────────

            # Cue 6: Select source layer in FILTERING tab
            NarrationCue(
                label="Sélection couche source",
                text=(
                    "Maintenant, configurons la couche source. "
                    "Je sélectionne la couche départements "
                    "dans l'onglet Filtering."
                ),
                sync="during",
                actions=lambda: (
                    self._log.info("Switching to FILTERING tab"),
                    app.select_tab("FILTERING"),
                    app.wait(0.5),
                    self._log.info("Selecting source layer 'departements'"),
                    app.select_layer("departements", index=1),
                ),
                post_delay=0.5,
            ),
            # Cue 7: Activate auto current layer sync
            NarrationCue(
                label="Activation synchro couche source",
                text=(
                    "J'active la synchronisation avec le panneau de couches QGIS. "
                    "Ce bouton lie la couche source à la sélection dans l'arbre des couches."
                ),
                sync="during",
                actions=lambda: activate_auto_current_layer(),
                post_delay=0.5,
            ),
            # Cue 8: Click communes in layer panel
            NarrationCue(
                label="Clic couche communes",
                text=(
                    "Je clique sur communes dans le panneau des couches. "
                    "La couche source se met à jour automatiquement."
                ),
                sync="during",
                actions=lambda: click_layer_communes(),
                post_delay=0.5,
            ),
            # Cue 9: Click back on departements
            NarrationCue(
                label="Retour couche départements",
                text=(
                    "Je reviens sur départements. "
                    "La synchronisation est immédiate."
                ),
                sync="during",
                actions=lambda: click_layer_departements(),
                post_delay=0.5,
            ),
            # Cue 10: Change display field via mouse
            NarrationCue(
                label="Changement champ d'affichage",
                text=(
                    "De retour dans l'onglet Exploration, "
                    "je change le champ d'affichage."
                ),
                sync="during",
                actions=lambda: (
                    self._log.info("Setting display field to 'NOM_DEPT'"),
                    pyautogui.click(
                        regions["exploring_display_field_combo"]["x"],
                        regions["exploring_display_field_combo"]["y"],
                        duration=move_dur,
                    ),
                    app.wait(0.3),
                    pyautogui.hotkey("ctrl", "a"),
                    app.wait(0.1),
                    app.type_text_unicode("NOM_DEPT"),
                    app.wait(0.5),
                    pyautogui.press("enter"),
                    app.wait(0.5),
                ),
                post_delay=0.5,
            ),
            # Cue 11: Browse feature picker with keyboard
            NarrationCue(
                label="Parcours feature picker clavier",
                text=(
                    "Je clique dans le sélecteur d'entités "
                    "et je navigue avec les flèches du clavier."
                ),
                sync="during",
                actions=lambda: (
                    self._log.info("Clicking into feature picker combo"),
                    pyautogui.click(
                        regions["exploring_feature_selector"]["x"],
                        regions["exploring_feature_selector"]["y"],
                        duration=move_dur,
                    ),
                    app.wait(0.5),
                    pyautogui.press("down"),
                    app.wait(0.8),
                    pyautogui.press("down"),
                    app.wait(0.8),
                ),
                post_delay=0.5,
            ),
            # Cue 12: Navigate with next/prev buttons
            NarrationCue(
                label="Navigation next/prev",
                text=(
                    "Avec le bouton précédent, je passe au département d'avant, "
                    "puis suivant pour revenir. "
                    "La navigation est immédiate."
                ),
                sync="during",
                actions=lambda: click_prev_then_next(),
                post_delay=0.5,
            ),
            # Cue 13: Diagram
            NarrationCue(
                label="Diagramme auto-détection",
                text="C'est automatique.",
                sync="during",
                actions=lambda: self.show_diagram_and_return(
                    obs, app, "v01_display_field_detection", duration=5.0
                ),
                post_delay=0.5,
            ),
        ]
