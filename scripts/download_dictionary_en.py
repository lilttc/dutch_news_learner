#!/usr/bin/env python3
"""
Merge English glosses into dutch_glosses.json from an English Wiktionary extract.

The English Wiktionary (en.wiktionary.org) has Dutch entries with English definitions.
Kaikki does not provide a direct en-extract download; use --input with a local file.

To get the data: run Wiktextract on the enwiktionary dump, or use the deprecated
postprocessed file from https://kaikki.org/dictionary/English/ (if available).

Alternatively, use --fallback to merge from a simple JSON file:
  {"goedkoop": "cheap", "makkelijk": "easy", ...}

Usage:
    python scripts/download_dictionary.py   # Run first to create dutch_glosses.json
    python scripts/download_dictionary_en.py --input path/to/en-extract.jsonl.gz
    python scripts/download_dictionary_en.py --fallback path/to/dutch_english.json
"""

import argparse
import gzip
import json
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DICT_DIR = Path(__file__).resolve().parent.parent / "data" / "dictionary"

# Map Wiktionary pos to normalized form
POS_MAP = {
    "noun": "NOUN", "n": "NOUN", "proper noun": "NOUN",
    "verb": "VERB", "v": "VERB",
    "adj": "ADJ", "adjective": "ADJ",
    "adv": "ADV", "adverb": "ADV",
}


def normalize_pos(pos: str) -> str:
    key = (pos or "").lower().strip()
    if "noun" in key:
        return "NOUN"
    if "verb" in key:
        return "VERB"
    if "adj" in key or "adjective" in key:
        return "ADJ"
    if "adv" in key or "adverb" in key:
        return "ADV"
    return POS_MAP.get(key, "OTHER")


def extract_dutch_entry(entry: dict) -> list[tuple]:
    """Extract (lemma, pos, gloss_en) for Dutch entries. Gloss is in English."""
    lang = (entry.get("lang") or "").lower()
    lang_code = (entry.get("lang_code") or "").lower()
    if "dutch" not in lang and lang_code not in ("nl", "dut"):
        return []

    word = entry.get("word")
    if not word or not isinstance(word, str):
        return []

    lemma = word.lower().strip()
    entry_pos = normalize_pos(entry.get("pos", ""))

    senses = entry.get("senses", [])
    if not senses:
        return []

    results = []
    for sense in senses:
        if sense.get("form_of") or sense.get("alt_of"):
            continue
        glosses = sense.get("glosses", [])
        if not glosses:
            continue
        gloss = glosses[0] if isinstance(glosses[0], str) else str(glosses[0])
        gloss = gloss.strip()
        if gloss:
            results.append((lemma, entry_pos, gloss))
        break
    return results


def merge_from_fallback(data: dict, fallback_path: Path) -> int:
    """Merge from a simple JSON {lemma: english} file."""
    with open(fallback_path, encoding="utf-8") as f:
        fallback = json.load(f)
    merged = 0
    for lemma, gloss_en in fallback.items():
        lemma = lemma.lower().strip()
        if lemma not in data:
            continue
        poses = data[lemma]
        if isinstance(poses, str):
            continue
        for pdata in poses.values() if isinstance(poses, dict) else []:
            if isinstance(pdata, dict) and not pdata.get("gloss_en"):
                pdata["gloss_en"] = str(gloss_en)
                merged += 1
                break
    return merged


def main():
    parser = argparse.ArgumentParser(
        description="Merge English glosses into dutch_glosses.json"
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to en-extract.jsonl or .jsonl.gz (English Wiktionary extract)",
    )
    parser.add_argument(
        "--fallback",
        type=Path,
        help="Path to JSON file with {lemma: english} mappings",
    )
    args = parser.parse_args()

    dict_path = DICT_DIR / "dutch_glosses.json"
    if not dict_path.exists():
        print("Run python scripts/download_dictionary.py first.")
        sys.exit(1)

    with open(dict_path, encoding="utf-8") as f:
        data = json.load(f)

    if args.fallback:
        if not args.fallback.exists():
            print(f"Error: {args.fallback} not found.")
            sys.exit(1)
        merged = merge_from_fallback(data, args.fallback)
        with open(dict_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=0)
        print(f"Merged {merged} English glosses from fallback file.")
        print("Restart the app to see English meanings.")
        return

    if not args.input or not args.input.exists():
        print("Error: Kaikki does not provide en-extract at a stable URL (404).")
        print()
        print("Options:")
        print("  1. Use --fallback with a JSON file:")
        print("     python scripts/download_dictionary_en.py --fallback data/dictionary/dutch_english_fallback.json")
        print("  2. Run Wiktextract on the enwiktionary dump and use --input")
        print()
        print("The app has a built-in fallback for common words. To add more, edit")
        print("data/dictionary/dutch_english_fallback.json and run with --fallback.")
        sys.exit(1)

    input_path = args.input
    print("Processing en-extract for Dutch entries...")
    merged = 0
    open_fn = gzip.open if str(input_path).endswith(".gz") else open
    mode = "rt" if str(input_path).endswith(".gz") else "r"

    with open_fn(input_path, mode, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                for lemma, pos, gloss_en in extract_dutch_entry(entry):
                    if lemma not in data:
                        continue
                    poses = data[lemma]
                    if isinstance(poses, str):
                        continue
                    # Prefer matching pos; else fill first empty gloss_en
                    if pos in poses:
                        pdata = poses[pos]
                        if isinstance(pdata, dict) and not pdata.get("gloss_en"):
                            pdata["gloss_en"] = gloss_en
                            merged += 1
                    else:
                        for p, pdata in poses.items():
                            if isinstance(pdata, dict) and not pdata.get("gloss_en"):
                                pdata["gloss_en"] = gloss_en
                                merged += 1
                                break
                    if merged % 5000 == 0 and merged:
                        print(f"  Merged {merged} English glosses...")
            except json.JSONDecodeError:
                continue

    with open(dict_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)

    print(f"Merged {merged} English glosses into {dict_path}")
    print("Restart the app to see English meanings.")


if __name__ == "__main__":
    main()
