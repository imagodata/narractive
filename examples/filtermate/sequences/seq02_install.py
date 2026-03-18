"""
Séquence 2 — INSTALLATION RAPIDE (0:30)
=========================================
Visuel: QGIS → Plugins → Rechercher "FilterMate" → Installer.
Diagramme 2 (backends & compatibilité) affiché.
"""

from __future__ import annotations

from video_automation.sequences.base import VideoSequence


class Seq02Install(VideoSequence):
    name = "Installation Rapide"
    sequence_id = "seq02"
    duration_estimate = 30.0
    obs_scene = "App Fullscreen"
    diagram_ids = ["02_backends"]
    narration_text = (
        "Installation en 3 clics depuis le dépôt officiel QGIS. "
        "Pour les bases PostgreSQL, un simple pip install psycopg2-binary suffit. "
        "FilterMate fonctionne sur Windows, Linux et macOS."
    )

    def execute(self, obs, app, config):
        """
        Navigate to Plugins menu, search for FilterMate, highlight Install button.
        Then show the backends diagram.
        """
        import pyautogui  # type: ignore

        app.focus_app()
        app.wait(1.0)

        # 1. Click the Plugins menu in QGIS menu bar
        #    (Typical QGIS layout: File | Edit | View | Layer | Settings | Plugins | Vector...)
        #    Use Alt+P to open Plugins menu
        pyautogui.press("alt")
        app.wait(0.3)
        # Navigate to Plugins in the menu bar
        # This is environment-specific; using a direct hotkey approach
        pyautogui.hotkey("alt", "p")  # Open Plugins menu
        app.wait(0.5)

        # Arrow down to "Manage and Install Plugins..."
        pyautogui.press("down")
        app.wait(0.2)
        pyautogui.press("return")
        app.wait(2.0)

        # 2. The Plugin Manager dialog is open — type in the search box
        #    (The search box is usually focused by default in newer QGIS)
        pyautogui.typewrite("FilterMate", interval=0.08)
        app.wait(1.5)

        # 3. Highlight the result — mouse to the plugin entry in the list
        #    (Exact coordinates depend on screen resolution; use a safe central area)
        app.move_mouse_to(640, 400, duration=0.8)
        app.wait(1.0)

        # 4. Point at Install button area (bottom right of dialog)
        app.move_mouse_to(900, 700, duration=0.8)
        app.wait(1.5)

        # 5. Close dialog without actually installing (this is a demo)
        pyautogui.press("escape")
        app.wait(1.0)

        # 6. Show backends / compatibility diagram
        self.show_diagram(obs, "02_backends", duration=8.0)

        # 7. Return to QGIS
        app.focus_app()
        app.wait(1.0)
