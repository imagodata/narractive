"""
Séquence 7 — MULTI-BACKEND COULISSES (0:45)
============================================
Visuel: Animation — même requête → 4 backends → chronométrages.
Diagramme 8 (Sélection Automatique du Backend) affiché.
"""

from __future__ import annotations

from narractive.sequences.base import VideoSequence


class Seq07Backends(VideoSequence):
    name = "Multi-Backend — Coulisses"
    sequence_id = "seq07"
    duration_estimate = 45.0
    obs_scene = "App + Panel"
    diagram_ids = ["08_backends"]
    narration_text = (
        "Derrière l'interface simple, FilterMate embarque 4 backends optimisés. "
        "Il choisit automatiquement le meilleur selon le type de votre source de données. "
        "Pour PostgreSQL : vues matérialisées et requêtes parallèles. "
        "Pour Spatialite : index R-tree. "
        "Et pour tout le reste : le backend OGR universel."
    )

    def execute(self, obs, app, config):
        """
        This sequence is mostly diagram-driven. We briefly show QGIS,
        then dive into diagram animations.
        """
        app.focus_app()
        app.wait(1.0)

        # 1. Show a quick filter on different layer types to illustrate auto-selection
        app.focus_panel()
        app.select_tab("FILTERING")
        app.wait(0.5)

        # Demonstrate selecting a PostgreSQL layer (if available)
        app.select_layer("routes")  # PostgreSQL layer
        app.wait(1.0)

        # 2. Display the backend selection diagram — main content of this sequence
        self.show_diagram(obs, "08_backends", duration=20.0)

        # 3. Return to QGIS
        app.focus_app()
        app.wait(1.0)
