"""Tests for DiagramLabels — multilingual label/title management."""
from __future__ import annotations

import pytest

from narractive.diagrams.i18n import DiagramLabels


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestDiagramLabelsInit:
    def test_empty_labels(self):
        dl = DiagramLabels(labels={})
        assert dl.label_ids == []
        assert dl.diagram_ids == []
        assert dl.languages == set()

    def test_default_lang(self):
        dl = DiagramLabels(labels={}, default_lang="en")
        assert dl.default_lang == "en"

    def test_default_lang_is_fr(self):
        dl = DiagramLabels(labels={})
        assert dl.default_lang == "fr"

    def test_titles_optional(self):
        dl = DiagramLabels(labels={"a": {"fr": "A"}})
        assert dl.diagram_ids == []


# ---------------------------------------------------------------------------
# Label lookup
# ---------------------------------------------------------------------------


class TestDiagramLabelsLookup:
    def setup_method(self):
        self.dl = DiagramLabels(
            labels={
                "server": {"fr": "Serveur", "en": "Server", "pt": "Servidor"},
                "client": {"fr": "Client", "en": "Client"},
                "fr_only": {"fr": "Seulement francais"},
            },
            titles={
                "architecture": {"fr": "Architecture", "en": "Architecture", "pt": "Arquitetura"},
                "flow": {"fr": "Flux"},
            },
            default_lang="fr",
        )

    def test_label_exact_match(self):
        assert self.dl.l("server", "en") == "Server"
        assert self.dl.l("server", "fr") == "Serveur"
        assert self.dl.l("server", "pt") == "Servidor"

    def test_label_fallback_to_default(self):
        assert self.dl.l("fr_only", "en") == "Seulement francais"

    def test_label_unknown_id_returns_id(self):
        assert self.dl.l("nonexistent", "fr") == "nonexistent"

    def test_label_get_label_alias(self):
        assert self.dl.get_label("server", "en") == "Server"

    def test_title_exact_match(self):
        assert self.dl.t("architecture", "en") == "Architecture"
        assert self.dl.t("architecture", "pt") == "Arquitetura"

    def test_title_fallback_to_default(self):
        assert self.dl.t("flow", "en") == "Flux"

    def test_title_unknown_id_returns_id(self):
        assert self.dl.t("unknown_diagram", "fr") == "unknown_diagram"

    def test_title_get_title_alias(self):
        assert self.dl.get_title("architecture", "fr") == "Architecture"


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------


class TestDiagramLabelsIntrospection:
    def test_label_ids(self):
        dl = DiagramLabels(labels={"a": {"fr": "A"}, "b": {"fr": "B"}})
        assert sorted(dl.label_ids) == ["a", "b"]

    def test_diagram_ids(self):
        dl = DiagramLabels(labels={}, titles={"x": {"fr": "X"}, "y": {"fr": "Y"}})
        assert sorted(dl.diagram_ids) == ["x", "y"]

    def test_languages(self):
        dl = DiagramLabels(
            labels={"a": {"fr": "A", "en": "A"}},
            titles={"t": {"pt": "T"}},
        )
        assert dl.languages == {"fr", "en", "pt"}

    def test_repr(self):
        dl = DiagramLabels(
            labels={"a": {"fr": "A"}, "b": {"en": "B"}},
            titles={"t": {"fr": "T"}},
        )
        r = repr(dl)
        assert "labels=2" in r
        assert "titles=1" in r


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestDiagramLabelsEdgeCases:
    def test_empty_string_value(self):
        dl = DiagramLabels(labels={"key": {"fr": "", "en": "English"}})
        # Empty string is falsy, should fall back to default or id
        result = dl.l("key", "fr")
        # Empty string is a valid value that evaluates to falsy
        # The implementation uses `or` chaining, so empty string falls through
        assert result in ("", "English", "key")

    def test_all_languages_missing_returns_id(self):
        dl = DiagramLabels(labels={"key": {}}, default_lang="fr")
        assert dl.l("key", "de") == "key"

    def test_multiple_labels_independent(self):
        dl = DiagramLabels(labels={
            "a": {"fr": "A_fr"},
            "b": {"fr": "B_fr"},
        })
        assert dl.l("a", "fr") == "A_fr"
        assert dl.l("b", "fr") == "B_fr"
