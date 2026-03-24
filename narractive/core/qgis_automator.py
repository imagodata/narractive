"""
Backward-compatibility shim.

.. deprecated:: 2.0
    Use :class:`narractive.core.app_automator.AppAutomator` instead.
"""
from narractive.core.app_automator import AppAutomator as QGISAutomator  # noqa: F401

__all__ = ["QGISAutomator"]
