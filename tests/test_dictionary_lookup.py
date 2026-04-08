"""
Tests for src/dictionary/lookup.py - DictionaryLookup (SQLite + JSON backends).

Key regression guard: lookup() returns the Dutch gloss, lookup_with_example()
returns gloss_en (English). These must never be conflated - confusing them was
the root cause of Dutch definitions appearing in the English translation field.
"""

import json
import sqlite3
from pathlib import Path

from src.dictionary.lookup import DictionaryLookup, FALLBACK_GLOSS_EN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sqlite_db(tmp_path: Path, rows: list[tuple]) -> Path:
    """Create a minimal glosses.db with the given (lemma, pos, gloss, gloss_en, example) rows."""
    db_path = tmp_path / "glosses.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE glosses (lemma TEXT, pos TEXT, gloss TEXT, gloss_en TEXT, example TEXT)"
    )
    conn.executemany("INSERT INTO glosses VALUES (?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# Existing tests (preserved)
# ---------------------------------------------------------------------------


def test_json_fallback_lookup(tmp_path: Path) -> None:
    glossary = {
        "gaan": {
            "VERB": {
                "gloss": "to go",
                "gloss_en": "to go",
                "example": "Ik ga naar school.",
            }
        }
    }
    json_path = tmp_path / "glosses.json"
    json_path.write_text(json.dumps(glossary, ensure_ascii=False), encoding="utf-8")

    lookup = DictionaryLookup(db_path=tmp_path / "missing.db", json_path=json_path)
    assert lookup.is_loaded
    assert lookup.lookup("gaan", pos="VERB") == "to go"

    result = lookup.lookup_with_example("gaan", pos="VERB")
    assert result is not None
    assert result["gloss"] == "to go"
    assert result["gloss_en"] == "to go"
    assert result["example"] == "Ik ga naar school."
    assert "Mijnwoordenboek" in lookup.get_links("gaan")


def test_sqlite_lookup_prefers_pos_and_falls_back(tmp_path: Path) -> None:
    db_path = _make_sqlite_db(
        tmp_path,
        [
            ("gaan", "VERB", "to go", "to go", "Ik ga naar school."),
        ],
    )
    lookup = DictionaryLookup(db_path=db_path)
    assert lookup.is_loaded
    assert lookup.lookup("gaan", pos="VERB") == "to go"
    assert lookup.lookup("gaan", pos="NOUN") == "to go"
    result = lookup.lookup_with_example("gaan", pos="VERB")
    assert result is not None
    assert result["gloss_en"] == "to go"


# ---------------------------------------------------------------------------
# Regression: gloss (Dutch) vs gloss_en (English) must never be conflated
# ---------------------------------------------------------------------------


def test_lookup_returns_dutch_gloss_not_english(tmp_path: Path) -> None:
    """lookup() returns the Dutch definition - this is correct for 'Meaning:' in the bubble."""
    db_path = _make_sqlite_db(
        tmp_path,
        [
            (
                "houden",
                "VERB",
                "niet laten varen, het bezit ervan niet verliezen",
                "to keep, preserve",
                None,
            ),
        ],
    )
    lookup = DictionaryLookup(db_path=db_path)
    assert lookup.lookup("houden", pos="VERB") == "niet laten varen, het bezit ervan niet verliezen"


def test_lookup_with_example_returns_english_gloss_en(tmp_path: Path) -> None:
    """lookup_with_example() gloss_en must be English - used for 'English:' in the bubble."""
    db_path = _make_sqlite_db(
        tmp_path,
        [
            (
                "houden",
                "VERB",
                "niet laten varen, het bezit ervan niet verliezen",
                "to keep, preserve",
                None,
            ),
        ],
    )
    lookup = DictionaryLookup(db_path=db_path)
    result = lookup.lookup_with_example("houden", pos="VERB")
    assert result is not None
    assert result["gloss"] == "niet laten varen, het bezit ervan niet verliezen"
    assert result["gloss_en"] == "to keep, preserve"
    # gloss and gloss_en must be different - if equal, Dutch leaked into English field
    assert result["gloss"] != result["gloss_en"]


# ---------------------------------------------------------------------------
# POS fallback chain
# ---------------------------------------------------------------------------


def test_pos_exact_match_preferred(tmp_path: Path) -> None:
    db_path = _make_sqlite_db(
        tmp_path,
        [
            ("bank", "NOUN", "a bench", "bench", None),
            ("bank", "OTHER", "financial institution", "bank", None),
        ],
    )
    lookup = DictionaryLookup(db_path=db_path)
    assert lookup.lookup("bank", pos="NOUN") == "a bench"


def test_pos_falls_back_to_other(tmp_path: Path) -> None:
    db_path = _make_sqlite_db(
        tmp_path,
        [
            ("bank", "OTHER", "financial institution", "bank", None),
        ],
    )
    lookup = DictionaryLookup(db_path=db_path)
    assert lookup.lookup("bank", pos="VERB") == "financial institution"


def test_pos_falls_back_to_first_row(tmp_path: Path) -> None:
    db_path = _make_sqlite_db(
        tmp_path,
        [
            ("bank", "NOUN", "a bench", "bench", None),
        ],
    )
    lookup = DictionaryLookup(db_path=db_path)
    # Unknown POS → first available row
    assert lookup.lookup("bank", pos="ADV") == "a bench"


# ---------------------------------------------------------------------------
# FALLBACK_GLOSS_EN
# ---------------------------------------------------------------------------


def test_fallback_gloss_en_used_when_sqlite_has_no_gloss_en(tmp_path: Path) -> None:
    """When SQLite has a Dutch gloss but no gloss_en, FALLBACK_GLOSS_EN supplies English."""
    db_path = _make_sqlite_db(
        tmp_path,
        [
            ("gaan", "VERB", "bewegen naar een plek", None, None),
        ],
    )
    lookup = DictionaryLookup(db_path=db_path)
    result = lookup.lookup_with_example("gaan", pos="VERB")
    assert result is not None
    assert result["gloss_en"] == FALLBACK_GLOSS_EN["gaan"]


def test_fallback_gloss_en_not_used_when_gloss_en_present(tmp_path: Path) -> None:
    """If gloss_en is in SQLite, FALLBACK_GLOSS_EN must not override it."""
    db_path = _make_sqlite_db(
        tmp_path,
        [
            ("gaan", "VERB", "bewegen", "to go somewhere", None),
        ],
    )
    lookup = DictionaryLookup(db_path=db_path)
    result = lookup.lookup_with_example("gaan", pos="VERB")
    assert result["gloss_en"] == "to go somewhere"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_unknown_word_returns_none(tmp_path: Path) -> None:
    db_path = _make_sqlite_db(
        tmp_path,
        [
            ("gaan", "VERB", "to go", "to go", None),
        ],
    )
    lookup = DictionaryLookup(db_path=db_path)
    assert lookup.lookup("xyznonexistent") is None
    assert lookup.lookup_with_example("xyznonexistent") is None


def test_get_links_returns_all_three(tmp_path: Path) -> None:
    lookup = DictionaryLookup(db_path=tmp_path / "missing.db")
    links = lookup.get_links("houden")
    assert "Mijnwoordenboek" in links
    assert "Woorden.org" in links
    assert "Wiktionary" in links
    assert "houden" in links["Mijnwoordenboek"]
    assert "houden" in links["Wiktionary"]


def test_lookup_case_insensitive(tmp_path: Path) -> None:
    db_path = _make_sqlite_db(
        tmp_path,
        [
            ("houden", "VERB", "to keep", "to keep", None),
        ],
    )
    lookup = DictionaryLookup(db_path=db_path)
    assert lookup.lookup("Houden", pos="VERB") == "to keep"
    assert lookup.lookup("HOUDEN", pos="VERB") == "to keep"
