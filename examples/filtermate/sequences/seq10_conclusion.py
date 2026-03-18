"""
Séquence 10 — CONCLUSION + CALL TO ACTION (0:20)
=================================================
Visuel: Logo FilterMate, liens GitHub / QGIS Plugin Store / docs.
"""

from __future__ import annotations

from video_automation.sequences.base import VideoSequence


class Seq10Conclusion(VideoSequence):
    name = "Conclusion + Call to Action"
    sequence_id = "seq10"
    duration_estimate = 20.0
    obs_scene = "Outro"
    diagram_ids = []
    narration_text = (
        "FilterMate est disponible gratuitement sur le dépôt officiel QGIS. "
        "Le code source est sur GitHub, la documentation sur le site dédié. "
        "Installez-le, essayez-le, et si ça vous est utile — "
        "laissez une étoile sur GitHub. À bientôt !"
    )

    def setup(self, obs, app, config):
        obs.transition_to_outro()
        app.wait(1.0)

    def execute(self, obs, app, config):
        """
        Show the outro scene with links displayed.
        The outro scene in OBS contains a Browser Source or Image with:
          - FilterMate logo
          - GitHub: https://github.com/imagodata/filter_mate
          - QGIS Plugins: https://plugins.app.org/plugins/filter_mate
          - Documentation: https://imagodata.github.io/filter_mate
        """
        # Display the outro for the narration duration
        app.wait(18.0)
        self._log.info(
            "CTA links:\n"
            "  GitHub: https://github.com/imagodata/filter_mate\n"
            "  QGIS:   https://plugins.app.org/plugins/filter_mate\n"
            "  Docs:   https://imagodata.github.io/filter_mate"
        )

    def teardown(self, obs, app, config):
        # Fade to black / end
        app.wait(2.0)
        self._log.info("Video production complete!")
