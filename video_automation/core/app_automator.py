"""
App Automator
=============
Controls a desktop application and its UI panels via PyAutoGUI.

Usage:
    from video_automation.core.app_automator import AppAutomator
    app = AppAutomator(config)
    app.focus_app()
    app.click_at("my_button")

Notes
-----
- pyautogui.FAILSAFE is True: move mouse to top-left corner to abort immediately.
- All coordinates are absolute screen pixels. Run calibrate.py first.
- Supports both Windows (win32gui) and headless Linux (xdotool/Xvfb).
"""

from __future__ import annotations

import logging
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import pyautogui  # type: ignore

    pyautogui.FAILSAFE = True
except ImportError as exc:
    raise ImportError("pyautogui is not installed. Run: pip install pyautogui") from exc


def _is_headless() -> bool:
    """Detect if we're running in a headless/Docker environment."""
    return os.environ.get("DISPLAY", "").startswith(":") and sys.platform != "win32"


class AppAutomator:
    """
    Automates desktop application interaction via PyAutoGUI.

    Supports both:
    - **Windows mode**: win32gui for window focus (original behavior)
    - **Headless mode** (Docker/Xvfb): xdotool for window management

    Parameters
    ----------
    config : dict
        Full config dict loaded from config.yaml.
    """

    def __init__(self, config: dict) -> None:
        self.app_cfg: dict = config.get("app", {})
        self.timing: dict = config.get("timing", {})
        self.window_title: str = self.app_cfg.get("window_title", "")
        self.panel_name: str = self.app_cfg.get("panel_name", "")
        self.regions: dict = self.app_cfg.get("regions", {})
        self._assets_dir = Path(__file__).parent.parent / "assets" / "buttons"
        self.headless: bool = _is_headless()

        # Apply global timing from config
        pyautogui.PAUSE = self.timing.get("click_delay", 0.3)
        mode = "headless/xdotool" if self.headless else "desktop/win32"
        logger.debug("AppAutomator initialised (PAUSE=%.2fs, mode=%s)", pyautogui.PAUSE, mode)

    # ------------------------------------------------------------------
    # Window focus
    # ------------------------------------------------------------------

    def focus_app(self) -> None:
        """Bring the application window to the foreground."""
        if self.headless:
            self._focus_xdotool(self.window_title)
        elif sys.platform == "win32":
            self._focus_win32(self.window_title)
        else:
            logger.warning(
                "Non-Windows platform detected. Please ensure the target app is in the foreground."
            )
        wait_time = self.app_cfg.get("startup_wait", 3)
        self.wait(wait_time)

    # Backward-compatible alias
    focus_qgis = focus_app

    def focus_panel(self) -> None:
        """Click on the side panel / dock widget to ensure it has focus."""
        dock = self.regions.get("plugin_dock", {})
        if dock:
            cx = dock.get("x", 0) + dock.get("width", 400) // 2
            cy = dock.get("y", 0) + 30  # Title bar area
            pyautogui.click(cx, cy, duration=self.timing.get("mouse_move_duration", 0.5))
            logger.debug("Clicked plugin dock at (%d, %d)", cx, cy)
        else:
            logger.warning("Panel dock region not calibrated.")

    # Backward-compatible alias
    focus_plugin_panel = focus_panel

    def _focus_win32(self, title_substring: str) -> None:
        """Use win32gui to find and bring window to front."""
        try:
            import win32con  # type: ignore
            import win32gui  # type: ignore

            def _enum_cb(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    text = win32gui.GetWindowText(hwnd)
                    if title_substring.lower() in text.lower():
                        results.append(hwnd)

            hwnds: list[int] = []
            win32gui.EnumWindows(_enum_cb, hwnds)
            if not hwnds:
                raise RuntimeError(f"No window found with title containing '{title_substring}'")
            hwnd = hwnds[0]
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            win32gui.SetForegroundWindow(hwnd)
            logger.info("Focused window (hwnd=%d).", hwnd)
        except ImportError:
            logger.warning("pywin32 not available. Skipping win32 focus.")
        except Exception as exc:
            logger.error("Failed to focus window: %s", exc)

    def _focus_xdotool(self, title_substring: str) -> None:
        """Use xdotool to find and bring window to front (headless/Linux)."""
        if not shutil.which("xdotool"):
            logger.warning("xdotool not available. Skipping focus.")
            return
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", title_substring],
                capture_output=True,
                text=True,
                timeout=5,
            )
            wids = result.stdout.strip().split("\n")
            wids = [w for w in wids if w]
            if not wids:
                logger.warning("No window found with title containing '%s'", title_substring)
                return
            wid = wids[0]
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", wid],
                check=True,
                timeout=5,
            )
            subprocess.run(
                ["xdotool", "windowfocus", "--sync", wid],
                check=True,
                timeout=5,
            )
            subprocess.run(
                ["xdotool", "windowsize", wid, "1920", "1080"],
                timeout=5,
            )
            subprocess.run(
                ["xdotool", "windowmove", wid, "0", "0"],
                timeout=5,
            )
            logger.info("Focused window via xdotool (wid=%s).", wid)
        except Exception as exc:
            logger.error("Failed to focus window via xdotool: %s", exc)

    # ------------------------------------------------------------------
    # Region-based clicks
    # ------------------------------------------------------------------

    def click_at(self, region_name: str, offset_x: int = 0, offset_y: int = 0) -> None:
        """
        Click the centre of a named calibrated region.

        Parameters
        ----------
        region_name : str
            Key from config.yaml app.regions.
        offset_x, offset_y : int
            Additional pixel offset from the centre.
        """
        region = self.regions.get(region_name)
        if region is None:
            raise ValueError(f"Region '{region_name}' not found in config. Run calibrate.py first.")
        if "width" in region:
            cx = region["x"] + region["width"] // 2 + offset_x
            cy = region["y"] + region["height"] // 2 + offset_y
        else:
            cx = region["x"] + offset_x
            cy = region["y"] + offset_y
        self.move_mouse_to(cx, cy)
        pyautogui.click()
        logger.debug("Clicked region '%s' at (%d, %d)", region_name, cx, cy)

    def click_at_xy(self, x: int, y: int) -> None:
        """Click at absolute screen coordinates."""
        self.move_mouse_to(x, y)
        pyautogui.click()
        logger.debug("Clicked at (%d, %d)", x, y)

    # ------------------------------------------------------------------
    # Image-based clicks (fallback for dynamic UI elements)
    # ------------------------------------------------------------------

    def click_button(self, button_name: str, confidence: float = 0.85) -> bool:
        """
        Locate and click a button by image template matching.

        Images must exist in assets/buttons/<button_name>.png.
        Returns True if found and clicked, False otherwise.
        """
        img_path = self._assets_dir / f"{button_name}.png"
        if not img_path.exists():
            logger.warning(
                "Button image not found: %s. Use screenshot tool to capture it.", img_path
            )
            return False
        try:
            location = pyautogui.locateOnScreen(str(img_path), confidence=confidence)
            if location is None:
                logger.warning("Button '%s' not found on screen.", button_name)
                return False
            cx, cy = pyautogui.center(location)
            self.move_mouse_to(cx, cy)
            pyautogui.click()
            logger.info("Clicked image button '%s' at (%d, %d)", button_name, cx, cy)
            return True
        except Exception as exc:
            logger.error("Image click failed for '%s': %s", button_name, exc)
            return False

    # ------------------------------------------------------------------
    # Generic UI interactions
    # ------------------------------------------------------------------

    def select_combobox_by_arrow(
        self,
        region_name: str,
        index: int,
    ) -> None:
        """Select an item in a non-editable combobox using arrow-key navigation.

        Parameters
        ----------
        region_name : str
            Calibrated region key for the combobox.
        index : int
            1-based position of the desired item in the dropdown list.
        """
        region = self.regions.get(region_name)
        if region is None:
            logger.warning("Combobox region '%s' not calibrated.", region_name)
            return
        pyautogui.click(
            region["x"],
            region["y"],
            duration=self.timing.get("mouse_move_duration", 0.5),
        )
        self.wait(0.3)
        pyautogui.click(region["x"], region["y"])
        self.wait(0.5)
        for _ in range(index):
            pyautogui.press("down")
            self.wait(0.15)
        pyautogui.press("return")
        self.wait(self.timing.get("action_pause", 0.5))
        logger.debug("Selected index %d in combobox '%s'", index, region_name)

    def select_combobox_item(
        self,
        region_name: str,
        item_text: str,
        double_click: bool = False,
    ) -> None:
        """Generic: click a combobox, clear, type item name, press Enter."""
        region = self.regions.get(region_name)
        if region:
            pyautogui.click(
                region["x"],
                region["y"],
                duration=self.timing.get("mouse_move_duration", 0.5),
            )
            if double_click:
                self.wait(0.3)
                pyautogui.click(region["x"], region["y"])
                self.wait(0.3)
            pyautogui.hotkey("ctrl", "a")
            self.type_text_unicode(item_text)
            self.wait(0.8)
            pyautogui.press("return")
            self.wait(self.timing.get("action_pause", 0.5))
            logger.debug("Selected '%s' in combobox '%s'", item_text, region_name)
        else:
            logger.warning("Combobox region '%s' not calibrated.", region_name)

    def toggle_section(self, pushbutton_region: str) -> None:
        """Click a checkable sidebar pushbutton to toggle its section."""
        region = self.regions.get(pushbutton_region)
        if region:
            pyautogui.click(
                region["x"], region["y"], duration=self.timing.get("mouse_move_duration", 0.5)
            )
            self.wait(0.8)
            logger.info("Toggled section: %s", pushbutton_region)
        else:
            logger.warning("Pushbutton '%s' not calibrated.", pushbutton_region)

    def expand_section(self, pushbutton_region: str, dependent_widget: str) -> None:
        """Expand a section if its dependent widget is not already visible."""
        btn = self.regions.get(pushbutton_region)
        if not btn:
            logger.warning("Pushbutton '%s' not calibrated.", pushbutton_region)
            return
        pyautogui.click(btn["x"], btn["y"], duration=self.timing.get("mouse_move_duration", 0.5))
        self.wait(0.8)
        logger.info("Expanded section: %s (dependent: %s)", pushbutton_region, dependent_widget)

    # ------------------------------------------------------------------
    # Text input
    # ------------------------------------------------------------------

    def type_text(self, text: str, interval: float | None = None) -> None:
        """Type text with natural keystroke timing."""
        if interval is None:
            interval = self.timing.get("type_delay", 0.05)
        pyautogui.typewrite(text, interval=interval)
        logger.debug("Typed: %r", text)

    def type_text_unicode(self, text: str) -> None:
        """Type unicode text (accented characters etc.) via clipboard paste."""
        try:
            import pyperclip  # type: ignore

            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        except ImportError:
            logger.warning("pyperclip not available; using typewrite (may fail for unicode).")
            self.type_text(text)
        logger.debug("Pasted unicode text: %r", text)

    # ------------------------------------------------------------------
    # Scrolling
    # ------------------------------------------------------------------

    def scroll_down(self, clicks: int = 3) -> None:
        """Scroll down in the currently focused widget."""
        for _ in range(clicks):
            pyautogui.scroll(-3)
            time.sleep(self.timing.get("scroll_delay", 0.2))
        logger.debug("Scrolled down %d clicks", clicks)

    def scroll_up(self, clicks: int = 3) -> None:
        """Scroll up in the currently focused widget."""
        for _ in range(clicks):
            pyautogui.scroll(3)
            time.sleep(self.timing.get("scroll_delay", 0.2))
        logger.debug("Scrolled up %d clicks", clicks)

    # ------------------------------------------------------------------
    # Mouse movement
    # ------------------------------------------------------------------

    def move_mouse_to(self, x: int, y: int, duration: float | None = None) -> None:
        """Move the mouse smoothly to absolute screen coordinates."""
        if duration is None:
            duration = self.timing.get("mouse_move_duration", 0.5)
        pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeOutQuad)

    def highlight_area(self, region_name: str, duration: float = 2.0) -> None:
        """Draw attention to a region by slowly circling the mouse around it."""
        region = self.regions.get(region_name) if isinstance(region_name, str) else region_name
        if region is None:
            logger.warning("highlight_area: region '%s' not found.", region_name)
            return
        cx = region.get("x", 0) + region.get("width", 100) // 2
        cy = region.get("y", 0) + region.get("height", 60) // 2
        radius = min(region.get("width", 80), region.get("height", 60)) * 0.4

        steps = 60
        step_delay = duration / steps
        for i in range(steps + 1):
            angle = 2 * math.pi * i / steps
            nx = int(cx + radius * math.cos(angle))
            ny = int(cy + radius * math.sin(angle))
            pyautogui.moveTo(nx, ny, duration=step_delay)
        logger.debug("Highlighted region '%s' for %.1fs", region_name, duration)

    # ------------------------------------------------------------------
    # Timing helpers
    # ------------------------------------------------------------------

    def wait(self, seconds: float) -> None:
        """Sleep with a periodic progress log for long waits."""
        if seconds <= 0:
            return
        if seconds <= 2:
            time.sleep(seconds)
        else:
            logger.info("Waiting %.1fs...", seconds)
            time.sleep(seconds)

    # ------------------------------------------------------------------
    # Application menu navigation
    # ------------------------------------------------------------------

    def open_menu_item(self, menu_region: str, item_region: str) -> None:
        """Open a menu and click an item by calibrated region names."""
        region = self.regions.get(menu_region)
        if region:
            pyautogui.click(
                region["x"],
                region["y"],
                duration=self.timing.get("mouse_move_duration", 0.5),
            )
        self.wait(0.5)
        region_item = self.regions.get(item_region)
        if region_item:
            pyautogui.click(
                region_item["x"],
                region_item["y"],
                duration=self.timing.get("mouse_move_duration", 0.5),
            )
        self.wait(1.0)
        logger.info("Opened menu %s > %s", menu_region, item_region)

    def open_plugin_manager(self) -> None:
        """Convenience: open plugin/extension manager dialog."""
        menu = self.regions.get("menu_extensions")
        if menu:
            self.open_menu_item("menu_extensions", "menu_extensions_manage")
        else:
            pyautogui.hotkey("alt", "e")
            self.wait(0.5)
            pyautogui.press("g")
            self.wait(0.2)
            pyautogui.press("return")
        self.wait(2.0)
        logger.info("Opened Plugin Manager")

    def close_dialog(self) -> None:
        """Close the currently focused dialog with Escape."""
        pyautogui.press("escape")
        self.wait(0.5)
        logger.debug("Closed dialog")

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def hover_region(self, region_name: str, duration: float = 1.5) -> None:
        """Move mouse to a region center and pause (no click)."""
        region = self.regions.get(region_name)
        if region is None:
            logger.warning("hover_region: '%s' not found.", region_name)
            return
        if "width" in region:
            cx = region["x"] + region["width"] // 2
            cy = region["y"] + region["height"] // 2
        else:
            cx = region["x"]
            cy = region["y"]
        self.move_mouse_to(cx, cy)
        self.wait(duration)
        logger.debug("Hovered region '%s' for %.1fs", region_name, duration)

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def screenshot(self, filepath: str) -> str:
        """Capture a full-screen screenshot and save to filepath."""
        if self.headless:
            display = os.environ.get("DISPLAY", ":99")
            try:
                subprocess.run(
                    ["import", "-display", display, "-window", "root", "-silent", filepath],
                    check=True,
                    capture_output=True,
                    timeout=5,
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                subprocess.run(
                    ["scrot", "-o", filepath],
                    check=True,
                    capture_output=True,
                    timeout=5,
                    env={**os.environ, "DISPLAY": display},
                )
        else:
            from PIL import ImageGrab  # type: ignore

            img = ImageGrab.grab()
            img.save(filepath)
        logger.info("Screenshot saved: %s", filepath)
        return filepath
