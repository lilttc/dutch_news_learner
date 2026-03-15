"""
Dutch dictionary lookup — lemma to English gloss, POS-aware.

Loads from pre-processed JSON (from Kaikki Wiktionary Dutch extract).
Uses POS to return correct meaning (e.g. olie+NOUN=oil, not verb form).
Provides authoritative external links (Mijnwoordenboek, Woorden.org, Wiktionary) for all lookups.
"""

import json
from pathlib import Path
from typing import Optional

# Path to dictionary data (populated by scripts/download_dictionary.py)
DEFAULT_DICT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "dictionary" / "dutch_glosses.json"

# Authoritative Dutch dictionary URLs (Van Dale free dictionary discontinued 2025)
MIJNWOORDENBOEK_URL = "https://www.mijnwoordenboek.nl/vertaal/NL/EN/{word}"  # Dutch-English
WOORDEN_ORG_URL = "https://www.woorden.org/woord/{word}"
WIKTIONARY_URL = "https://en.wiktionary.org/wiki/{word}"

# Fallback English glosses when nl Wiktionary has none (common words)
FALLBACK_GLOSS_EN: dict[str, str] = {
    "goedkoop": "cheap",
    "goedkoper": "cheaper",
    "makkelijk": "easy",
    "makkelijker": "easier",
    "duur": "expensive",
    "duurder": "more expensive",
    "gaan": "to go",
    "komen": "to come",
    "gebruiken": "to use",
    "olie": "oil",
    "water": "water",
    "land": "country",
    "landen": "countries",
    "brandstof": "fuel",
    "prijs": "price",
    "prijzen": "prices",
    "fatbike": "fat bike",
    "fatbikes": "fat bikes",
    "verboden": "forbidden",
    "advies": "advice",
    "inwoner": "resident",
    "inwoners": "residents",
}


class DictionaryLookup:
    """
    Lookup Dutch lemmas to English glosses, POS-aware.

    Structure: {lemma: {pos: {gloss, example}}}.
    Uses pos to avoid wrong meanings (e.g. "olie" noun vs verb form).
    """

    def __init__(self, dict_path: Optional[Path] = None):
        """
        Initialize lookup. Loads dictionary from JSON if available.

        Args:
            dict_path: Path to dutch_glosses.json. Default: data/dictionary/dutch_glosses.json
        """
        self._cache: dict = {}
        path = dict_path or DEFAULT_DICT_PATH
        if path.exists():
            with open(path, encoding="utf-8") as f:
                self._cache = json.load(f)

    def lookup(self, lemma: str, pos: Optional[str] = None) -> Optional[str]:
        """
        Get English gloss for a Dutch lemma. POS-aware for correct meaning.

        Args:
            lemma: Dutch word (lemma form, lowercase preferred).
            pos: Part of speech (NOUN, VERB, ADJ, ADV). If provided, prefers matching entry.

        Returns:
            English gloss/translation, or None if not found.
        """
        entry = self._get_entry(lemma, pos)
        if entry is None:
            return None
        if isinstance(entry, str):
            return entry
        return entry.get("gloss")

    def _get_entry(self, lemma: str, pos: Optional[str] = None):
        """Get raw entry for lemma (optionally by pos). Handles legacy flat format."""
        key = lemma.lower().strip()
        if key not in self._cache:
            return None
        poses = self._cache[key]
        if isinstance(poses, str):
            return poses  # Legacy flat format
        if pos and pos in poses:
            return poses[pos]
        if pos and "OTHER" in poses:
            return poses["OTHER"]  # Fallback for unmapped POS
        return next(iter(poses.values()), None) if poses else None

    def lookup_with_example(self, lemma: str, pos: Optional[str] = None) -> Optional[dict]:
        """
        Get gloss, English gloss (when available), and example sentence.
        Returns {gloss, gloss_en, example} or None.
        Prefers dictionary example (from Wiktionary) when available.
        Uses FALLBACK_GLOSS_EN when dictionary has no English.
        """
        entry = self._get_entry(lemma, pos)
        gloss = None
        gloss_en = None
        example = None
        if entry is not None:
            if isinstance(entry, str):
                gloss = entry
            else:
                gloss = entry.get("gloss")
                gloss_en = entry.get("gloss_en") or None
                example = entry.get("example") or None
        if gloss_en is None:
            gloss_en = FALLBACK_GLOSS_EN.get(lemma.lower().strip())
        if entry is None and gloss_en is None:
            return None
        return {
            "gloss": gloss,
            "gloss_en": gloss_en,
            "example": example,
        }

    def get_links(self, lemma: str) -> dict[str, str]:
        """
        Get authoritative dictionary links for a Dutch word.

        Returns:
            Dict of source name -> URL.
        """
        word = lemma.strip()
        return {
            "Mijnwoordenboek": MIJNWOORDENBOEK_URL.format(word=word),
            "Woorden.org": WOORDEN_ORG_URL.format(word=word),
            "Wiktionary": WIKTIONARY_URL.format(word=word),
        }

    @property
    def is_loaded(self) -> bool:
        """True if dictionary data has been loaded."""
        return len(self._cache) > 0


# Module-level singleton (lazy)
_lookup: Optional[DictionaryLookup] = None


def get_lookup() -> DictionaryLookup:
    """Get shared DictionaryLookup instance."""
    global _lookup
    if _lookup is None:
        _lookup = DictionaryLookup()
    return _lookup
