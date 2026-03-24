"""
Diagram Internationalization (i18n)
====================================
Base class for managing multilingual labels and titles in Mermaid diagrams.

Projects extend ``DiagramLabels`` with their own label dictionaries to
produce localized diagram definitions.

Usage::

    from narractive.diagrams.i18n import DiagramLabels

    labels = DiagramLabels(
        labels={
            "server": {"fr": "Serveur", "en": "Server", "pt": "Servidor"},
            "client": {"fr": "Client",  "en": "Client", "pt": "Cliente"},
        },
        titles={
            "architecture": {"fr": "Architecture", "en": "Architecture"},
        },
        default_lang="fr",
    )

    name = labels.l("server", "en")       # "Server"
    title = labels.t("architecture", "pt") # "Architecture" (fallback to fr)
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DiagramLabels:
    """
    Multilingual label manager for Mermaid diagrams.

    Provides ``l()`` (label) and ``t()`` (title) helpers with automatic
    fallback to the default language when a translation is missing.

    Parameters
    ----------
    labels : dict[str, dict[str, str]]
        Mapping of ``label_id → {lang: translation}``.
    titles : dict[str, dict[str, str]], optional
        Mapping of ``diagram_id → {lang: title}``.
    default_lang : str
        Fallback language code (default ``"fr"``).
    """

    def __init__(
        self,
        labels: dict[str, dict[str, str]],
        titles: Optional[dict[str, dict[str, str]]] = None,
        default_lang: str = "fr",
    ) -> None:
        self._labels = labels
        self._titles = titles or {}
        self.default_lang = default_lang

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def l(self, label_id: str, lang: str) -> str:  # noqa: E741 — single-letter method
        """
        Get a translated label with fallback.

        Parameters
        ----------
        label_id : str
            Key in the labels dictionary.
        lang : str
            Desired language code.

        Returns
        -------
        str
            Translated label, or fallback, or the raw ``label_id``.
        """
        return self.get_label(label_id, lang)

    def t(self, diagram_id: str, lang: str) -> str:
        """
        Get a translated diagram title with fallback.

        Parameters
        ----------
        diagram_id : str
            Key in the titles dictionary.
        lang : str
            Desired language code.

        Returns
        -------
        str
            Translated title, or fallback, or the raw ``diagram_id``.
        """
        return self.get_title(diagram_id, lang)

    def get_label(self, label_id: str, lang: str) -> str:
        """Look up a label with fallback to ``default_lang``, then ``label_id``."""
        entry = self._labels.get(label_id)
        if entry is None:
            logger.debug("Unknown label_id: %s", label_id)
            return label_id
        return entry.get(lang) or entry.get(self.default_lang) or label_id

    def get_title(self, diagram_id: str, lang: str) -> str:
        """Look up a diagram title with fallback to ``default_lang``."""
        entry = self._titles.get(diagram_id)
        if entry is None:
            logger.debug("Unknown diagram_id: %s", diagram_id)
            return diagram_id
        return entry.get(lang) or entry.get(self.default_lang) or diagram_id

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def label_ids(self) -> list[str]:
        """Return all registered label IDs."""
        return list(self._labels.keys())

    @property
    def diagram_ids(self) -> list[str]:
        """Return all registered diagram IDs."""
        return list(self._titles.keys())

    @property
    def languages(self) -> set[str]:
        """Return the set of all language codes found across labels."""
        langs: set[str] = set()
        for entry in self._labels.values():
            langs.update(entry.keys())
        for entry in self._titles.values():
            langs.update(entry.keys())
        return langs

    def __repr__(self) -> str:
        return (
            f"<DiagramLabels labels={len(self._labels)} "
            f"titles={len(self._titles)} "
            f"langs={sorted(self.languages)}>"
        )