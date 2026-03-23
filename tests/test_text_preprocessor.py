"""Tests for TextPreprocessor."""

from __future__ import annotations

from video_automation.core.text_preprocessor import TextPreprocessor

CUSTOM_CONFIG = {
    "acronyms": {
        "QGIS": {"fr": "Q. GIS", "en": "Q. GIS"},
    },
    "spelled": {
        "PDF": {"fr": "pe-de-effe", "en": "P-D-F"},
    },
    "proper_nouns": {
        "QField": {"fr": "kioufilede", "en": "~"},
    },
}


class TestAcronymExpansion:
    def test_acronym_expansion_fr(self):
        pp = TextPreprocessor(config=CUSTOM_CONFIG)
        result = pp.preprocess("Ouvrez QGIS maintenant", lang="fr")
        assert "Q. GIS" in result
        assert "QGIS" not in result

    def test_acronym_expansion_en(self):
        pp = TextPreprocessor(config=CUSTOM_CONFIG)
        result = pp.preprocess("Open QGIS now", lang="en")
        assert "Q. GIS" in result
        assert "QGIS" not in result


class TestSpelledSigle:
    def test_spelled_sigle_fr(self):
        pp = TextPreprocessor(config=CUSTOM_CONFIG)
        result = pp.preprocess("Ouvrez le fichier PDF", lang="fr")
        assert "pe-de-effe" in result
        assert "PDF" not in result

    def test_spelled_sigle_en(self):
        pp = TextPreprocessor(config=CUSTOM_CONFIG)
        result = pp.preprocess("Open the PDF file", lang="en")
        assert "P-D-F" in result
        assert "PDF" not in result

    def test_default_config_pdf(self):
        """Default config should spell out PDF as P-D-F."""
        pp = TextPreprocessor()
        result = pp.preprocess("Open the PDF file", lang="en")
        assert "P-D-F" in result


class TestNumberVerbalization:
    def test_number_fr_73(self):
        pp = TextPreprocessor()
        result = pp.preprocess("73 fichiers", lang="fr")
        assert "septante-trois" in result

    def test_number_en_73(self):
        pp = TextPreprocessor()
        result = pp.preprocess("73 files", lang="en")
        assert "seventy-three" in result

    def test_number_fr_100(self):
        pp = TextPreprocessor()
        result = pp.preprocess("100 elements", lang="fr")
        assert "cent" in result


class TestPercentage:
    def test_percentage_fr(self):
        pp = TextPreprocessor()
        result = pp.preprocess("73% des fichiers", lang="fr")
        assert "septante-trois pour cent" in result

    def test_percentage_en(self):
        pp = TextPreprocessor()
        result = pp.preprocess("73% of files", lang="en")
        assert "seventy-three percent" in result


class TestProperNounProtection:
    def test_tilde_keeps_word_as_is(self):
        """'~' means keep as-is (protected) for that language."""
        pp = TextPreprocessor(config=CUSTOM_CONFIG)
        result = pp.preprocess("Use QField on the field", lang="en")
        # QField maps to "~" in en -> should be preserved as "QField"
        assert "QField" in result

    def test_proper_noun_replaced_in_fr(self):
        pp = TextPreprocessor(config=CUSTOM_CONFIG)
        result = pp.preprocess("Utilisez QField sur le terrain", lang="fr")
        assert "kioufilede" in result
        assert "QField" not in result


class TestNoneConfig:
    def test_none_config_uses_defaults(self):
        pp = TextPreprocessor(config=None)
        result = pp.preprocess("Open PDF and GPS data", lang="en")
        assert "P-D-F" in result
        assert "G-P-S" in result

    def test_none_config_numbers(self):
        pp = TextPreprocessor(config=None)
        result = pp.preprocess("There are 10 items", lang="fr")
        assert "dix" in result


class TestUnknownLanguage:
    def test_unknown_lang_falls_back_gracefully(self):
        """Unknown language should not raise; falls back to FR number dict."""
        pp = TextPreprocessor(config=CUSTOM_CONFIG)
        result = pp.preprocess("Il y a 10 elements", lang="zh")
        assert isinstance(result, str)

    def test_unknown_lang_no_crash_percentage(self):
        pp = TextPreprocessor()
        result = pp.preprocess("50% complete", lang="xx")
        assert isinstance(result, str)
