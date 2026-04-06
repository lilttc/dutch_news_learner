from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.dictionary.lookup import DictionaryLookup


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
    db_path = tmp_path / "glosses.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE glosses (lemma TEXT, pos TEXT, gloss TEXT, gloss_en TEXT, example TEXT)"
    )
    conn.execute(
        "INSERT INTO glosses (lemma, pos, gloss, gloss_en, example) VALUES (?, ?, ?, ?, ?)",
        ("gaan", "VERB", "to go", "to go", "Ik ga naar school."),
    )
    conn.commit()
    conn.close()

    lookup = DictionaryLookup(db_path=db_path)
    assert lookup.is_loaded
    assert lookup.lookup("gaan", pos="VERB") == "to go"
    assert lookup.lookup("gaan", pos="NOUN") == "to go"
    result = lookup.lookup_with_example("gaan", pos="VERB")
    assert result is not None
    assert result["gloss_en"] == "to go"
