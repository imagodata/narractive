"""Tests for the DiagramLabels i18n module."""
from __future__ import annotations

from video_automation.diagrams.i18n import DiagramLabels


class TestDiagramLabels:
    def setup_method(self):
        self.labels = DiagramLabels(
            labels={
                "server": {"fr": "Serveur", "en": "Server", "pt": "Servidor"},
                "client": {"fr": "Client", "en": "Client", "pt": "Cliente"},
                "empty": {"fr": "Vide"},
            },
            titles={
                "architecture": {"fr": "Architecture", "en": "Architecture"},
                "overview": {"fr": "Vue d'ensemble"},
            },
            default_lang="fr",
        )

    def test_label_known_lang(self):
        assert self.labels.l("server", "en") == "Server"

    def test_label_default_lang(self):
        assert self.labels.l("server", "fr") == "Serveur"

    def test_label_unknown_lang_fallback(self):
        """Unknown lang should fallback to default_lang."""
        assert self.labels.l("server", "de") == "Serveur"

    def test_label_unknown_id(self):
        """Unknown label_id returns the id itself."""
        assert self.labels.l("unknown_key", "fr") == "unknown_key"

    def test_title_known_lang(self):
        assert self.labels.t("architecture", "en") == "Architecture"

    def test_title_fallback(self):
        assert self.labels.t("overview", "en") == "Vue d'ensemble"

    def test_title_unknown_id(self):
        assert self.labels.t("nonexistent", "fr") == "nonexistent"

    def test_get_label_same_as_l(self):
        assert self.labels.get_label("client", "pt") == self.labels.l("client", "pt")

    def test_get_title_same_as_t(self):
        assert self.labels.get_title("architecture", "fr") == self.labels.t("architecture", "fr")


class TestDiagramLabelsIntrospection:
    def setup_method(self):
        self.labels = DiagramLabels(
            labels={"a": {"fr": "A", "en": "A"}, "b": {"pt": "B"}},
            titles={"t1": {"fr": "T1", "de": "T1"}},
            default_lang="fr",
        )

    def test_label_ids(self):
        assert set(self.labels.label_ids) == {"a", "b"}

    def test_diagram_ids(self):
        assert self.labels.diagram_ids == ["t1"]

    def test_languages(self):
        assert self.labels.languages == {"fr", "en", "pt", "de"}

    def test_repr(self):
        r = repr(self.labels)
        assert "labels=2" in r
        assert "titles=1" in r


class TestDiagramLabelsEmpty:
    def test_empty_labels(self):
        labels = DiagramLabels(labels={})
        assert labels.l("anything", "fr") == "anything"

    def test_no_titles(self):
        labels = DiagramLabels(labels={})
        assert labels.t("anything", "fr") == "anything"

    def test_empty_languages(self):
        labels = DiagramLabels(labels={})
        assert labels.languages == set()

    def test_custom_default_lang(self):
        labels = DiagramLabels(
            labels={"x": {"en": "X-en", "de": "X-de"}},
            default_lang="en",
        )
        # Requesting 'fr' should fallback to 'en' (default)
        assert labels.l("x", "fr") == "X-en"
