"""
Backward-compatibility shim.

.. deprecated:: 2.0
    Use :class:`video_automation.core.app_automator.AppAutomator` instead.
"""

from video_automation.core.app_automator import AppAutomator as QGISAutomator

__all__ = ["QGISAutomator"]
