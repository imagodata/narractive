"""
Text Preprocessor for TTS Engines
===================================
Transforms raw text before sending it to TTS engines to improve
pronunciation of acronyms, technical sigles, numbers, and proper nouns.

Supports per-language phonetic mappings loaded from a YAML configuration
block, with sensible built-in defaults for common terms.

Usage (standalone)::

    from video_automation.core.text_preprocessor import TextPreprocessor

    # With custom config (the 'pronunciation' section from config.yaml)
    preprocessor = TextPreprocessor(config=pronunciation_config)
    clean = preprocessor.preprocess("Open the PDF with QGIS 3", lang="fr")

    # With built-in defaults only
    preprocessor = TextPreprocessor()
    clean = preprocessor.preprocess("Upload 73% of the CSV files", lang="en")

Expected YAML configuration structure::

    pronunciation:
      acronyms:
        FTTH: {fr: "effe-te-te-ache", en: "ef-tee-tee-aitch"}
        QGIS: {fr: "Q. GIS", en: "Q. GIS"}
      spelled:
        PDF: {fr: "pe-de-effe", en: "pee-dee-ef"}
        CSV: {fr: "ce-esse-ve", en: "see-ess-vee"}
      proper_nouns:
        WYRE: {fr: "ouhayere", en: "~"}    # "~" means keep as-is (protected)
        QField: {fr: "kioufilede", en: "~"}

When ``config`` is ``None``, generic defaults are used (PDF, CSV, GPS only).
No domain-specific terms are included in defaults.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Number dictionaries — FR (Belgian: septante/nonante), EN, PT
# ---------------------------------------------------------------------------

_NUMBERS_FR: dict[str, str] = {
    "0": "zéro", "1": "un", "2": "deux", "3": "trois", "4": "quatre",
    "5": "cinq", "6": "six", "7": "sept", "8": "huit", "9": "neuf",
    "10": "dix", "11": "onze", "12": "douze", "13": "treize",
    "14": "quatorze", "15": "quinze", "16": "seize", "17": "dix-sept",
    "18": "dix-huit", "19": "dix-neuf", "20": "vingt",
    "21": "vingt et un", "22": "vingt-deux", "23": "vingt-trois",
    "24": "vingt-quatre", "25": "vingt-cinq", "26": "vingt-six",
    "27": "vingt-sept", "28": "vingt-huit", "29": "vingt-neuf",
    "30": "trente", "31": "trente et un", "32": "trente-deux",
    "33": "trente-trois", "40": "quarante", "50": "cinquante",
    "60": "soixante",
    "70": "septante", "71": "septante et un", "72": "septante-deux",
    "73": "septante-trois", "74": "septante-quatre", "75": "septante-cinq",
    "76": "septante-six", "77": "septante-sept", "78": "septante-huit",
    "79": "septante-neuf",
    "80": "quatre-vingts",
    "90": "nonante", "91": "nonante et un", "92": "nonante-deux",
    "93": "nonante-trois", "94": "nonante-quatre", "95": "nonante-cinq",
    "96": "nonante-six", "97": "nonante-sept", "98": "nonante-huit",
    "99": "nonante-neuf",
    "100": "cent",
    "200": "deux cents", "300": "trois cents", "400": "quatre cents",
    "450": "quatre cent cinquante", "500": "cinq cents",
    "1000": "mille",
}

_NUMBERS_EN: dict[str, str] = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
    "10": "ten", "11": "eleven", "12": "twelve", "13": "thirteen",
    "14": "fourteen", "15": "fifteen", "16": "sixteen", "17": "seventeen",
    "18": "eighteen", "19": "nineteen", "20": "twenty",
    "21": "twenty-one", "22": "twenty-two", "23": "twenty-three",
    "24": "twenty-four", "25": "twenty-five", "26": "twenty-six",
    "27": "twenty-seven", "28": "twenty-eight", "29": "twenty-nine",
    "30": "thirty", "31": "thirty-one", "32": "thirty-two",
    "33": "thirty-three", "40": "forty", "50": "fifty",
    "60": "sixty", "70": "seventy", "73": "seventy-three",
    "80": "eighty", "90": "ninety", "100": "one hundred",
    "200": "two hundred", "300": "three hundred", "400": "four hundred",
    "450": "four hundred and fifty", "500": "five hundred",
    "1000": "one thousand",
}

_NUMBERS_PT: dict[str, str] = {
    "0": "zero", "1": "um", "2": "dois", "3": "três", "4": "quatro",
    "5": "cinco", "6": "seis", "7": "sete", "8": "oito", "9": "nove",
    "10": "dez", "11": "onze", "12": "doze", "13": "treze",
    "14": "catorze", "15": "quinze", "16": "dezasseis", "17": "dezassete",
    "18": "dezoito", "19": "dezanove", "20": "vinte",
    "21": "vinte e um", "22": "vinte e dois", "23": "vinte e três",
    "24": "vinte e quatro", "25": "vinte e cinco", "26": "vinte e seis",
    "27": "vinte e sete", "28": "vinte e oito", "29": "vinte e nove",
    "30": "trinta", "31": "trinta e um", "32": "trinta e dois",
    "33": "trinta e três", "40": "quarenta", "50": "cinquenta",
    "60": "sessenta", "70": "setenta", "73": "setenta e três",
    "80": "oitenta", "90": "noventa", "100": "cem",
    "200": "duzentos", "300": "trezentos", "400": "quatrocentos",
    "450": "quatrocentos e cinquenta", "500": "quinhentos",
    "1000": "mil",
}

_NUMBERS_BY_LANG: dict[str, dict[str, str]] = {
    "fr": _NUMBERS_FR,
    "en": _NUMBERS_EN,
    "pt": _NUMBERS_PT,
}

_PERCENT_BY_LANG: dict[str, str] = {
    "fr": "pour cent",
    "en": "percent",
    "pt": "por cento",
}

# ---------------------------------------------------------------------------
# Default fallback dictionaries (generic, no domain-specific terms)
# ---------------------------------------------------------------------------

_DEFAULT_ACRONYMS: dict[str, str] = {}

_DEFAULT_SIGLES: dict[str, str] = {
    "PDF": "P-D-F",
    "CSV": "C-S-V",
    "GPS": "G-P-S",
}

_DEFAULT_PROPER_NOUNS: dict[str, str] = {}
_DEFAULT_PROTECTED: set[str] = set()


class TextPreprocessor:
    """
    Preprocess text for TTS engines to improve pronunciation.

    Handles acronyms, spelled-out sigles, proper nouns, and number-to-word
    conversion across multiple languages.

    Parameters
    ----------
    config : dict | None
        The ``pronunciation`` section from ``config.yaml``. Contains keys:
        ``acronyms``, ``spelled``, ``proper_nouns`` (each mapping a term to
        a dict of ``{lang: phonetic_form}``). Also supports a legacy
        ``protected`` key (flat list of words to keep as-is).
        If ``None``, built-in generic defaults are used.

    Examples
    --------
    >>> pp = TextPreprocessor()
    >>> pp.preprocess("Le fichier PDF contient 73% des donnees", lang="fr")
    'Le fichier P-D-F contient septante-trois pour cent des donnees'
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config
        logger.debug(
            "TextPreprocessor initialized %s",
            "with custom config" if config else "with built-in defaults",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def preprocess(self, text: str, lang: str = "fr") -> str:
        """
        Transform text for better TTS pronunciation.

        Processing pipeline:

        1. Protect proper nouns (marked with ``"~"``) using placeholders
        2. Replace proper nouns with their phonetic forms
        3. Replace acronyms with their phonetic forms
        4. Replace spelled sigles with their phonetic forms
        5. Replace ``<number>%`` with word form + "pour cent"/"percent"
        6. Replace standalone numbers with word form
        7. Restore protected nouns from placeholders

        Parameters
        ----------
        text : str
            Raw narration text.
        lang : str
            Language code (``"fr"``, ``"en"``, ``"pt"``). Defaults to ``"fr"``.

        Returns
        -------
        str
            Preprocessed text ready for TTS engine consumption.
        """
        acronyms, sigles, proper_nouns, protected = self._build_dictionaries(lang)
        numbers = _NUMBERS_BY_LANG.get(lang, _NUMBERS_FR)
        percent_word = _PERCENT_BY_LANG.get(lang, "pour cent")

        result = text

        # 1. Protect proper nouns with placeholders
        placeholders: dict[str, str] = {}
        for i, word in enumerate(sorted(protected)):
            placeholder = f"__PROTECTED_{i}__"
            placeholders[placeholder] = word
            result = re.sub(r"\b" + re.escape(word) + r"\b", placeholder, result)

        # 2. Replace proper nouns with phonetic forms
        # Sort by descending length to avoid partial replacements
        # (e.g., "GeoPackages" before "GeoPackage")
        for noun, phonetic_form in sorted(
            proper_nouns.items(), key=lambda x: -len(x[0])
        ):
            result = re.sub(
                r"\b" + re.escape(noun) + r"\b", phonetic_form, result
            )

        # 3. Replace acronyms with phonetic forms
        for acronym, phonetic_form in acronyms.items():
            result = re.sub(
                r"\b" + re.escape(acronym) + r"\b", phonetic_form, result
            )

        # 4. Replace spelled sigles with phonetic forms
        for sigle, phonetic_form in sigles.items():
            result = re.sub(
                r"\b" + re.escape(sigle) + r"\b", phonetic_form, result
            )

        # 5. Replace numbers followed by % with word form
        def _replace_number_percent(match: re.Match) -> str:
            num = match.group(1)
            if num in numbers:
                return f"{numbers[num]} {percent_word}"
            return match.group(0)

        result = re.sub(r"\b(\d+)%", _replace_number_percent, result)

        # 6. Replace standalone numbers with word form
        def _replace_number(match: re.Match) -> str:
            num = match.group(0)
            if num in numbers:
                return numbers[num]
            return num

        result = re.sub(r"\b\d+\b", _replace_number, result)

        # 7. Restore protected nouns
        for placeholder, word in placeholders.items():
            result = result.replace(placeholder, word)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_dictionaries(
        self, lang: str
    ) -> tuple[dict[str, str], dict[str, str], dict[str, str], set[str]]:
        """
        Build replacement dictionaries from config or fallback defaults.

        Parameters
        ----------
        lang : str
            Language code for phonetic lookup.

        Returns
        -------
        tuple
            ``(acronyms, sigles, proper_nouns, protected)`` where each dict
            maps a term to its phonetic replacement, and ``protected`` is a
            set of words to keep untouched.
        """
        if self._config is None:
            return (
                dict(_DEFAULT_ACRONYMS),
                dict(_DEFAULT_SIGLES),
                dict(_DEFAULT_PROPER_NOUNS),
                set(_DEFAULT_PROTECTED),
            )

        protected: set[str] = set()

        # -- Proper nouns --
        proper_nouns: dict[str, str] = {}
        for noun, langs in self._config.get("proper_nouns", {}).items():
            phonetic = langs.get(lang, "~")
            if phonetic == "~":
                protected.add(noun)
            else:
                proper_nouns[noun] = phonetic

        # Legacy: flat "protected" list
        for word in self._config.get("protected", []):
            protected.add(word)

        # -- Acronyms --
        acronyms: dict[str, str] = {}
        for acronym, langs in self._config.get("acronyms", {}).items():
            phonetic = langs.get(lang, "~")
            if phonetic == "~":
                protected.add(acronym)
            else:
                acronyms[acronym] = phonetic

        # -- Spelled sigles --
        sigles: dict[str, str] = {}
        for sigle, langs in self._config.get("spelled", {}).items():
            phonetic = langs.get(lang, "~")
            if phonetic == "~":
                protected.add(sigle)
            else:
                sigles[sigle] = phonetic

        return acronyms, sigles, proper_nouns, protected
