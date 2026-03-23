"""Tests for DiagramLabels i18n module."""

from __future__ import annotations

import pytest

from video_automation.diagrams.i18n import DiagramLabels

LABELS = {
    "server": {"fr": "Serveur", "en": "Server", "pt": "Servidor"},
    "client": {"fr": "Client", "en": "Client", "pt": "Cliente"},
}

TITLES = {
    "architecture": {"fr": "Architecture", "en": "Architecture"},
    "overview": {"fr": "Vue d'ensemble", "en": "Overview"},
}


@pytest.fixture
def labels():
    return DiagramLabels(labels=LABELS, titles=TITLES, default_lang="fr")


class TestLabelLookup:
    def test_known_lang(self, labels):
        assert labels.label("server", "en") == "Server"
        assert labels.label("server", "fr") == "Serveur"
        assert labels.label("server", "pt") == "Servidor"

    def test_unknown_lang_falls_back_to_default(self, labels):
        # "zh" not in labels -> should fall back to default_lang "fr"
        result = labels.label("server", "zh")
        assert result == "Serveur"

    def test_unknown_label_id_returns_label_id(self, labels):
        result = labels.label("nonexistent_label", "fr")
        assert result == "nonexistent_label"

    def test_unknown_label_id_unknown_lang(self, labels):
        result = labels.label("nonexistent", "zh")
        assert result == "nonexistent"


class TestTitleLookup:
    def test_title_known_lang(self, labels):
        assert labels.t("overview", "en") == "Overview"
        assert labels.t("overview", "fr") == "Vue d'ensemble"

    def test_title_fallback(self, labels):
        # "pt" not defined for "architecture" -> falls back to "fr"
        result = labels.t("architecture", "pt")
        assert result == "Architecture"

    def test_title_unknown_diagram_id(self, labels):
        result = labels.t("nonexistent_diagram", "fr")
        assert result == "nonexistent_diagram"


class TestProperties:
    def test_label_ids(self, labels):
        ids = labels.label_ids
        assert "server" in ids
        assert "client" in ids
        assert len(ids) == 2

    def test_diagram_ids(self, labels):
        ids = labels.diagram_ids
        assert "architecture" in ids
        assert "overview" in ids
        assert len(ids) == 2

    def test_languages(self, labels):
        langs = labels.languages
        assert "fr" in langs
        assert "en" in langs
        assert "pt" in langs

    def test_languages_empty_titles(self):
        dl = DiagramLabels(
            labels={"key": {"fr": "val"}},
            titles={},
        )
        assert "fr" in dl.languages


class TestRepr:
    def test_repr(self, labels):
        r = repr(labels)
        assert "DiagramLabels" in r
        assert "labels=2" in r
        assert "titles=2" in r

    def test_repr_no_titles(self):
        dl = DiagramLabels(labels={"a": {"fr": "b"}})
        r = repr(dl)
        assert "labels=1" in r
        assert "titles=0" in r


class TestDefaultLang:
    def test_custom_default_lang(self):
        dl = DiagramLabels(
            labels={"key": {"en": "Value", "fr": "Valeur"}},
            default_lang="en",
        )
        # Unknown lang should fall back to "en"
        result = dl.label("key", "zh")
        assert result == "Value"

    def test_default_lang_is_fr_by_default(self):
        dl = DiagramLabels(labels={"key": {"fr": "Valeur"}})
        assert dl.default_lang == "fr"
