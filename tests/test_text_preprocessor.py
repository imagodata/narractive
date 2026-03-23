"""Tests for the TextPreprocessor module."""
from __future__ import annotations

from video_automation.core.text_preprocessor import TextPreprocessor


class TestDefaultPreprocessor:
    """Tests using built-in defaults (no custom config)."""

    def setup_method(self):
        self.pp = TextPreprocessor()

    def test_default_sigles_pdf(self):
        result = self.pp.preprocess("Open the PDF file", lang="en")
        assert "P-D-F" in result

    def test_default_sigles_csv(self):
        result = self.pp.preprocess("Fichier CSV", lang="fr")
        assert "C-S-V" in result

    def test_default_sigles_gps(self):
        result = self.pp.preprocess("GPS coordinates", lang="en")
        assert "G-P-S" in result

    def test_number_replacement_fr(self):
        result = self.pp.preprocess("Il y a 3 fichiers", lang="fr")
        assert "trois" in result

    def test_number_replacement_en(self):
        result = self.pp.preprocess("There are 5 items", lang="en")
        assert "five" in result

    def test_number_replacement_pt(self):
        result = self.pp.preprocess("Existem 7 itens", lang="pt")
        assert "sete" in result

    def test_percentage_fr(self):
        result = self.pp.preprocess("73% des donnees", lang="fr")
        assert "septante-trois pour cent" in result

    def test_percentage_en(self):
        result = self.pp.preprocess("73% of data", lang="en")
        assert "seventy-three percent" in result

    def test_percentage_pt(self):
        result = self.pp.preprocess("73% dos dados", lang="pt")
        assert "setenta e três por cento" in result

    def test_unknown_number_kept(self):
        result = self.pp.preprocess("Code 99999", lang="fr")
        assert "99999" in result

    def test_no_change_plain_text(self):
        text = "Bonjour le monde"
        result = self.pp.preprocess(text, lang="fr")
        assert result == text

    def test_empty_text(self):
        result = self.pp.preprocess("", lang="fr")
        assert result == ""

    def test_multiple_replacements(self):
        result = self.pp.preprocess("Le fichier PDF contient 73% des donnees", lang="fr")
        assert "P-D-F" in result
        assert "septante-trois pour cent" in result


class TestCustomConfig:
    """Tests with custom pronunciation config."""

    def setup_method(self):
        self.config = {
            "acronyms": {
                "FTTH": {"fr": "effe-te-te-ache", "en": "ef-tee-tee-aitch"},
                "QGIS": {"fr": "Q. GIS", "en": "Q. GIS"},
            },
            "spelled": {
                "PDF": {"fr": "pe-de-effe", "en": "pee-dee-ef"},
            },
            "proper_nouns": {
                "WYRE": {"fr": "ouhayere", "en": "~"},
                "QField": {"fr": "kioufilede", "en": "~"},
            },
        }
        self.pp = TextPreprocessor(config=self.config)

    def test_acronym_fr(self):
        result = self.pp.preprocess("Installer FTTH", lang="fr")
        assert "effe-te-te-ache" in result

    def test_acronym_en(self):
        result = self.pp.preprocess("Deploy FTTH", lang="en")
        assert "ef-tee-tee-aitch" in result

    def test_spelled_sigle_fr(self):
        result = self.pp.preprocess("Ouvrir le PDF", lang="fr")
        assert "pe-de-effe" in result

    def test_proper_noun_replacement_fr(self):
        result = self.pp.preprocess("Utiliser QField", lang="fr")
        assert "kioufilede" in result

    def test_proper_noun_protected_en(self):
        """When phonetic is '~', the word should be kept as-is (protected)."""
        result = self.pp.preprocess("Use WYRE network", lang="en")
        assert "WYRE" in result

    def test_protected_via_tilde(self):
        result = self.pp.preprocess("Open QField app", lang="en")
        assert "QField" in result

    def test_legacy_protected_list(self):
        config = {"protected": ["FooBar"], "acronyms": {}, "spelled": {}, "proper_nouns": {}}
        pp = TextPreprocessor(config=config)
        result = pp.preprocess("Use FooBar now", lang="fr")
        assert "FooBar" in result

    def test_unknown_lang_falls_back(self):
        """Unknown lang for an acronym with '~' default should protect it."""
        result = self.pp.preprocess("Deploy FTTH", lang="de")
        # 'de' not in config -> falls back to '~' -> protected
        assert "FTTH" in result


class TestNumberVerbalization:
    """Tests for number-to-word conversion."""

    def setup_method(self):
        self.pp = TextPreprocessor()

    def test_zero(self):
        assert "zéro" in self.pp.preprocess("0 erreur", lang="fr")

    def test_large_number_fr(self):
        assert "mille" in self.pp.preprocess("1000 lignes", lang="fr")

    def test_hundred_en(self):
        assert "one hundred" in self.pp.preprocess("100 rows", lang="en")

    def test_number_not_in_dict(self):
        result = self.pp.preprocess("Il y a 42 items", lang="fr")
        # 42 is not in the FR dict, should be kept as-is
        assert "42" in result

    def test_belgian_french_70(self):
        result = self.pp.preprocess("70 dossiers", lang="fr")
        assert "septante" in result

    def test_belgian_french_90(self):
        result = self.pp.preprocess("90 projets", lang="fr")
        assert "nonante" in result
