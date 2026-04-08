#!/usr/bin/env python3
"""
Download English glosses for Dutch words from the English Wiktionary (via kaikki.org).

The English Wiktionary defines Dutch words with English glosses - exactly what learners
need. This script downloads the pre-extracted JSONL, filters for content words
(noun, verb, adj, adv), and merges English glosses into the existing dutch_glosses.json.

Source: https://kaikki.org/dictionary/Dutch/kaikki.org-dictionary-Dutch.jsonl
  - Extracted from enwiktionary (English Wiktionary)
  - ~229MB uncompressed, ~135k Dutch word entries with English definitions
  - Updated weekly by kaikki.org

Usage:
    python scripts/download_dictionary_en.py            # Download + merge
    python scripts/download_dictionary_en.py --dry-run  # Show stats without saving
    python scripts/download_dictionary_en.py --input local_copy.jsonl  # Use local file
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlretrieve

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DICT_DIR = Path(__file__).resolve().parent.parent / "data" / "dictionary"
GLOSSES_PATH = DICT_DIR / "dutch_glosses.json"
EN_EXTRACT_PATH = DICT_DIR / "en-wiktionary-dutch.jsonl"
DOWNLOAD_URL = "https://kaikki.org/dictionary/Dutch/kaikki.org-dictionary-Dutch.jsonl"

POS_MAP = {
    "noun": "NOUN",
    "verb": "VERB",
    "adj": "ADJ",
    "adv": "ADV",
}


def normalize_pos(pos: str) -> str:
    """Map Wiktionary pos string to spaCy-style tag (NOUN, VERB, ADJ, ADV)."""
    key = (pos or "").lower().strip()
    if "noun" in key:
        return "NOUN"
    if "verb" in key:
        return "VERB"
    if "adj" in key:
        return "ADJ"
    if "adv" in key:
        return "ADV"
    return POS_MAP.get(key, "OTHER")


def extract_english_gloss(entry: dict) -> list[tuple[str, str, str, str]]:
    """
    Extract (lemma, pos, gloss_en, example) from an EN Wiktionary Dutch entry.

    Skips form_of/alt_of senses (inflected forms like "ging" -> "past tense of gaan")
    to keep only canonical definitions.

    Returns:
        List of (lemma, normalized_pos, english_gloss, example_sentence) tuples.
    """
    word = entry.get("word")
    if not word or not isinstance(word, str):
        return []

    lemma = word.lower().strip()
    if len(lemma) < 2:
        return []

    pos = normalize_pos(entry.get("pos", ""))

    results = []
    for sense in entry.get("senses", []):
        if sense.get("form_of") or sense.get("alt_of"):
            continue

        glosses = sense.get("glosses", [])
        if not glosses:
            raw_glosses = sense.get("raw_glosses", [])
            if raw_glosses:
                glosses = raw_glosses

        if not glosses:
            continue

        gloss = str(glosses[0]).strip()
        if not gloss:
            continue

        example = None
        for ex in sense.get("examples", []):
            if isinstance(ex, dict):
                text = ex.get("text", "")
            elif isinstance(ex, str):
                text = ex
            else:
                continue
            if text and isinstance(text, str) and text.strip():
                example = text.strip()
                break

        results.append((lemma, pos, gloss, example))
        break  # Take the first non-form sense

    return results


def build_en_glosses(filepath: Path) -> dict[str, dict[str, dict]]:
    """
    Process the EN Wiktionary Dutch JSONL into {lemma: {pos: {gloss_en, example}}}.

    Returns:
        Nested dict: lemma -> pos -> {gloss_en, example}.
    """
    result: dict[str, dict[str, dict]] = {}
    count = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            for lemma, pos, gloss_en, example in extract_english_gloss(entry):
                if not lemma or not gloss_en:
                    continue
                if lemma not in result:
                    result[lemma] = {}
                if pos not in result[lemma]:
                    result[lemma][pos] = {
                        "gloss_en": gloss_en,
                        "example": example or "",
                    }
                    count += 1
                    if count % 10000 == 0:
                        print(f"  Extracted {count} entries...")

    print(f"  Total: {count} (lemma, pos) entries from EN Wiktionary")
    return result


def merge_into_glosses(existing: dict, en_data: dict) -> tuple[int, int]:
    """
    Merge EN Wiktionary English glosses into the existing dutch_glosses.json.

    Two merge strategies:
    1. Fill in missing gloss_en for entries already in the NL Wiktionary dict.
    2. Add entirely new entries that only exist in the EN Wiktionary.

    Returns:
        (enriched_count, new_count) - how many existing entries got gloss_en filled,
        and how many new lemma/pos entries were added.
    """
    enriched = 0
    new_entries = 0

    for lemma, poses in en_data.items():
        for pos, en_entry in poses.items():
            gloss_en = en_entry["gloss_en"]
            example = en_entry.get("example", "")

            if lemma in existing and isinstance(existing[lemma], dict):
                if pos in existing[lemma]:
                    pdata = existing[lemma][pos]
                    if isinstance(pdata, dict) and not pdata.get("gloss_en"):
                        pdata["gloss_en"] = gloss_en
                        if example and not pdata.get("example"):
                            pdata["example"] = example
                        enriched += 1
                else:
                    # POS exists in EN but not NL - add it
                    existing[lemma][pos] = {
                        "gloss": "",
                        "gloss_en": gloss_en,
                        "example": example,
                    }
                    new_entries += 1
            else:
                # Lemma not in NL Wiktionary at all - create new entry
                if lemma not in existing:
                    existing[lemma] = {}
                existing[lemma][pos] = {
                    "gloss": "",
                    "gloss_en": gloss_en,
                    "example": example,
                }
                new_entries += 1

    return enriched, new_entries


def main():
    parser = argparse.ArgumentParser(
        description="Download English glosses for Dutch words from EN Wiktionary"
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Use a local JSONL file instead of downloading",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show stats without saving changes",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=GLOSSES_PATH,
        help="Path to dutch_glosses.json",
    )
    args = parser.parse_args()

    DICT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Get the EN Wiktionary Dutch data
    if args.input and args.input.exists():
        input_path = args.input
        print(f"Using local file: {input_path}")
    else:
        input_path = EN_EXTRACT_PATH
        if input_path.exists():
            print(f"Using cached file: {input_path}")
        else:
            print("Downloading EN Wiktionary Dutch entries (~229MB)...")
            print(f"  URL: {DOWNLOAD_URL}")
            print("  (This may take a few minutes)")
            urlretrieve(DOWNLOAD_URL, input_path)
            print("  Download complete.")
    print()

    # Step 2: Extract English glosses
    print("Extracting English glosses from EN Wiktionary...")
    en_data = build_en_glosses(input_path)
    print()

    # Step 3: Load existing NL Wiktionary dictionary (if available)
    existing = {}
    if args.output.exists():
        print(f"Loading existing dictionary: {args.output}")
        with open(args.output, encoding="utf-8") as f:
            existing = json.load(f)
        existing_en_count = sum(
            1
            for poses in existing.values()
            if isinstance(poses, dict)
            for p in poses.values()
            if isinstance(p, dict) and p.get("gloss_en")
        )
        print(f"  {len(existing)} lemmas, {existing_en_count} already have gloss_en")
    else:
        print(f"No existing dictionary at {args.output} - creating from scratch.")
    print()

    # Step 4: Merge
    print("Merging English glosses...")
    enriched, new_entries = merge_into_glosses(existing, en_data)
    print(f"  Enriched (filled empty gloss_en): {enriched}")
    print(f"  New entries added: {new_entries}")

    final_en_count = sum(
        1
        for poses in existing.values()
        if isinstance(poses, dict)
        for p in poses.values()
        if isinstance(p, dict) and p.get("gloss_en")
    )
    print(f"  Total entries with English gloss: {final_en_count}")
    print()

    # Step 5: Save
    if args.dry_run:
        print("(Dry run - no changes saved)")
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=0)
        print(f"Saved to {args.output}")
        print()
        print("Restart the app to see updated English meanings.")


if __name__ == "__main__":
    main()
