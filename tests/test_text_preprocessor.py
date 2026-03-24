"""Tests for TextPreprocessor — pronunciation normalization for TTS."""
from __future__ import annotations

import pytest

from narractive.core.text_preprocessor import TextPreprocessor


# ---------------------------------------------------------------------------
# No-config (built-in defaults)
# ---------------------------------------------------------------------------


class TestTextPreprocessorDefaults:
    """Test TextPreprocessor with built-in defaults (no config)."""

    def setup_method(self):
        self.pp = TextPreprocessor()

    def test_default_sigle_pdf_replaced(self):
        result = self.pp.preprocess("Ouvrez le PDF", lang="fr")
        assert "P-D-F" in result

    def test_default_sigle_csv_replaced(self):
        result = self.pp.preprocess("Export CSV", lang="fr")
        assert "C-S-V" in result

    def test_default_sigle_gps_replaced(self):
        result = self.pp.preprocess("Signal GPS", lang="fr")
        assert "G-P-S" in result

    def test_number_to_word_fr(self):
        result = self.pp.preprocess("Il y a 3 fichiers", lang="fr")
        assert "trois" in result
        assert "3" not in result

    def test_number_to_word_en(self):
        result = self.pp.preprocess("There are 5 files", lang="en")
        assert "five" in result
        assert "5" not in result

    def test_number_to_word_pt(self):
        result = self.pp.preprocess("Existem 7 ficheiros", lang="pt")
        assert "sete" in result

    def test_percentage_fr(self):
        result = self.pp.preprocess("73% des donnees", lang="fr")
        assert "septante-trois pour cent" in result

    def test_percentage_en(self):
        result = self.pp.preprocess("50% complete", lang="en")
        assert "fifty percent" in result

    def test_percentage_pt(self):
        result = self.pp.preprocess("20% pronto", lang="pt")
        assert "vinte por cento" in result

    def test_unknown_number_left_as_is(self):
        result = self.pp.preprocess("Code 9999", lang="fr")
        assert "9999" in result

    def test_text_without_replacements_unchanged(self):
        text = "Bonjour le monde"
        result = self.pp.preprocess(text, lang="fr")
        assert result == text

    def test_empty_text(self):
        assert self.pp.preprocess("", lang="fr") == ""

    def test_multiple_numbers_replaced(self):
        result = self.pp.preprocess("De 1 a 10", lang="fr")
        assert "un" in result
        assert "dix" in result

    def test_belgian_french_septante(self):
        """Belgian French: 70 = septante, not soixante-dix."""
        result = self.pp.preprocess("Il y a 70 elements", lang="fr")
        assert "septante" in result

    def test_belgian_french_nonante(self):
        """Belgian French: 90 = nonante, not quatre-vingt-dix."""
        result = self.pp.preprocess("Il y a 90 elements", lang="fr")
        assert "nonante" in result


# ---------------------------------------------------------------------------
# With custom config
# ---------------------------------------------------------------------------


class TestTextPreprocessorConfig:
    """Test TextPreprocessor with custom pronunciation config."""

    def setup_method(self):
        self.config = {
            "acronyms": {
                "QGIS": {"fr": "Q. GIS", "en": "Q. GIS"},
                "FTTH": {"fr": "effe-te-te-ache", "en": "ef-tee-tee-aitch"},
            },
            "spelled": {
                "PDF": {"fr": "pe-de-effe", "en": "pee-dee-ef"},
                "CSV": {"fr": "ce-esse-ve", "en": "see-ess-vee"},
            },
            "proper_nouns": {
                "FilterMate": {"fr": "filtre-mette", "en": "~"},
                "GeoPackage": {"fr": "geo-packaje", "en": "~"},
            },
        }
        self.pp = TextPreprocessor(config=self.config)

    def test_acronym_replaced_fr(self):
        result = self.pp.preprocess("Ouvrez QGIS", lang="fr")
        assert "Q. GIS" in result

    def test_acronym_replaced_en(self):
        result = self.pp.preprocess("Open QGIS", lang="en")
        assert "Q. GIS" in result

    def test_spelled_sigle_replaced_fr(self):
        result = self.pp.preprocess("Le fichier PDF", lang="fr")
        assert "pe-de-effe" in result

    def test_spelled_sigle_replaced_en(self):
        result = self.pp.preprocess("The PDF file", lang="en")
        assert "pee-dee-ef" in result

    def test_proper_noun_replaced_fr(self):
        result = self.pp.preprocess("Lancez FilterMate", lang="fr")
        assert "filtre-mette" in result

    def test_proper_noun_protected_en(self):
        """When phonetic is '~', the word is protected (kept as-is)."""
        result = self.pp.preprocess("Open FilterMate now", lang="en")
        assert "FilterMate" in result

    def test_proper_noun_geopackage_protected_en(self):
        result = self.pp.preprocess("Use GeoPackage format", lang="en")
        assert "GeoPackage" in result

    def test_proper_noun_geopackage_replaced_fr(self):
        result = self.pp.preprocess("Format GeoPackage", lang="fr")
        assert "geo-packaje" in result

    def test_combined_replacements(self):
        text = "QGIS exporte 10 fichiers PDF en CSV"
        result = self.pp.preprocess(text, lang="fr")
        assert "Q. GIS" in result
        assert "pe-de-effe" in result
        assert "ce-esse-ve" in result
        assert "dix" in result

    def test_legacy_protected_list(self):
        config = {
            "protected": ["MySpecialWord"],
            "acronyms": {},
            "spelled": {},
            "proper_nouns": {},
        }
        pp = TextPreprocessor(config=config)
        result = pp.preprocess("Use MySpecialWord here", lang="fr")
        assert "MySpecialWord" in result

    def test_unknown_lang_falls_back_to_fr_numbers(self):
        """Unknown language should fall back to French number dictionaries."""
        result = self.pp.preprocess("Il y a 5 items", lang="xx")
        # Falls back to _NUMBERS_FR
        assert "cinq" in result

    def test_tilde_acronym_is_protected(self):
        """Acronyms with '~' phonetic should be protected."""
        config = {
            "acronyms": {"API": {"fr": "~", "en": "ay-pee-eye"}},
            "spelled": {},
            "proper_nouns": {},
        }
        pp = TextPreprocessor(config=config)
        result = pp.preprocess("Use the API", lang="fr")
        assert "API" in result

    def test_long_proper_nouns_replaced_before_short(self):
        """Longer proper nouns should be processed first to avoid partial matches."""
        config = {
            "acronyms": {},
            "spelled": {},
            "proper_nouns": {
                "Geo": {"fr": "jeo", "en": "~"},
                "GeoPackages": {"fr": "geo-packajes", "en": "~"},
                "GeoPackage": {"fr": "geo-packaje", "en": "~"},
            },
        }
        pp = TextPreprocessor(config=config)
        result = pp.preprocess("Export GeoPackages", lang="fr")
        assert "geo-packajes" in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestTextPreprocessorEdgeCases:
    def test_number_at_start_of_text(self):
        pp = TextPreprocessor()
        result = pp.preprocess("10 items found", lang="en")
        assert "ten" in result

    def test_number_at_end_of_text(self):
        pp = TextPreprocessor()
        result = pp.preprocess("Found items 10", lang="en")
        assert "ten" in result

    def test_number_in_percentage_not_duplicated(self):
        """A number followed by % should only be replaced once."""
        pp = TextPreprocessor()
        result = pp.preprocess("Resultat 50%", lang="fr")
        assert result.count("cinquante") == 1

    def test_number_zero(self):
        pp = TextPreprocessor()
        result = pp.preprocess("Value is 0", lang="en")
        assert "zero" in result

    def test_large_known_number(self):
        pp = TextPreprocessor()
        result = pp.preprocess("Total 1000 items", lang="fr")
        assert "mille" in result
