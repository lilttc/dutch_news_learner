#!/usr/bin/env python3
"""
Download and process Dutch dictionary from Kaikki Wiktionary extract.

Creates data/dictionary/dutch_glosses.json: (lemma, pos) -> {gloss, example}.
Uses POS to avoid wrong meanings (e.g. "olie" noun=oil vs verb=to oil).
Skips form_of/alt_of senses (inflected forms) in favor of main definitions.
Extracts usage examples when available.

Source: https://kaikki.org/dictionary/downloads/nl/nl-extract.jsonl.gz

Usage:
    python scripts/download_dictionary.py [--output PATH]
"""

import argparse
import gzip
import json
import sys
from pathlib import Path
from urllib.request import urlretrieve

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "dictionary" / "dutch_glosses.json"
DOWNLOAD_URL = "https://kaikki.org/dictionary/downloads/nl/nl-extract.jsonl.gz"

# Map Wiktionary pos to normalized form (for matching with spaCy)
POS_MAP = {
    "noun": "NOUN", "n": "NOUN", "proper noun": "NOUN", "proper-noun": "NOUN",
    "verb": "VERB", "v": "VERB",
    "adj": "ADJ", "adjective": "ADJ",
    "adv": "ADV", "adverb": "ADV",
}


def normalize_pos(pos: str) -> str:
    """Map Wiktionary pos to spaCy-style (NOUN, VERB, ADJ, ADV)."""
    if not pos:
        return "OTHER"
    key = pos.lower().strip()
    # Handle compound keys like "verb form", "noun phrase"
    if "noun" in key:
        return "NOUN"
    if "verb" in key:
        return "VERB"
    if "adj" in key or "adjective" in key:
        return "ADJ"
    if "adv" in key or "adverb" in key:
        return "ADV"
    return POS_MAP.get(key, "OTHER")


def extract_entry(entry: dict) -> list[tuple]:
    """
    Extract (lemma, pos, gloss, example) from a Kaikki entry.

    Skips senses that are form_of/alt_of (inflected forms) to prefer main definitions.
    Returns list of (lemma, pos, gloss, example) tuples.
    """
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
        # Skip inflected/form senses - they give wrong meanings (e.g. "olie" = "1st person of oliën")
        if sense.get("form_of") or sense.get("alt_of"):
            continue

        glosses = sense.get("glosses", [])
        if not glosses:
            continue

        gloss = glosses[0] if isinstance(glosses[0], str) else str(glosses[0])
        gloss = gloss.strip()
        if not gloss:
            continue

        # Extract first English translation (for Dutch words, gives English meaning)
        gloss_en = None
        translations = sense.get("translations") or entry.get("translations", [])
        for t in translations:
            if isinstance(t, dict) and t.get("code") == "en":
                w = t.get("word")
                if w and isinstance(w, str):
                    gloss_en = w.strip()
                    break
            # Also check "lang" for "English"
            if isinstance(t, dict) and t.get("lang", "").lower() == "english":
                w = t.get("word")
                if w and isinstance(w, str):
                    gloss_en = gloss_en or w.strip()

        # Extract first example if available
        example = None
        examples = sense.get("examples", [])
        if examples and isinstance(examples[0], dict):
            ex_text = examples[0].get("text")
            if ex_text and isinstance(ex_text, str):
                example = ex_text.strip()
        elif examples and isinstance(examples[0], str):
            example = examples[0].strip()

        results.append((lemma, entry_pos, gloss, example, gloss_en))
        break  # One sense per entry, prefer first non-form sense

    return results


def process_stream(filepath: Path) -> dict:
    """
    Build (lemma, pos) -> {gloss, example} map.

    For each (lemma, pos), keeps first valid entry. POS-aware to fix wrong meanings.
    """
    # Structure: {lemma: {pos: {gloss, example}}}
    result: dict = {}
    count = 0

    open_fn = gzip.open if str(filepath).endswith(".gz") else open
    mode = "rt" if str(filepath).endswith(".gz") else "r"
    encoding = "utf-8"

    with open_fn(filepath, mode, encoding=encoding) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                for lemma, pos, gloss, example, gloss_en in extract_entry(entry):
                    if lemma and gloss:
                        if lemma not in result:
                            result[lemma] = {}
                        # Prefer entry with matching pos; overwrite if we have a better one
                        if pos not in result[lemma] or not result[lemma][pos].get("gloss"):
                            result[lemma][pos] = {
                                "gloss": gloss,
                                "example": example or "",
                                "gloss_en": gloss_en or "",
                            }
                        count += 1
                        if count % 10000 == 0:
                            print(f"  Processed {count} entries...")
            except json.JSONDecodeError:
                continue

    return result


def main():
    parser = argparse.ArgumentParser(description="Download Dutch dictionary from Kaikki Wiktionary")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    parser.add_argument("--input", type=Path, help="Use local file instead of downloading")
    args = parser.parse_args()

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.input:
        input_path = args.input
        print(f"Processing local file: {input_path}")
    else:
        input_path = output_path.parent / "nl-extract.jsonl.gz"
        print(f"Downloading from {DOWNLOAD_URL}...")
        print("(This may take a few minutes, ~118MB compressed)")
        urlretrieve(DOWNLOAD_URL, input_path)
        print("Download complete. Processing...")

    result = process_stream(input_path)
    total = sum(len(poses) for poses in result.values())
    print(f"Extracted {total} (lemma, pos) entries for {len(result)} unique lemmas.")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=0)

    print(f"Saved to {output_path}")
    en_count = sum(
        1 for poses in result.values() for p in poses.values() if p.get("gloss_en")
    )
    if en_count:
        print(f"  ({en_count} entries include English gloss)")
    print()
    print("Next: python scripts/enrich_vocabulary.py  # Populate VocabularyItem.translation")
    print("(Optional: python scripts/download_dictionary_en.py --fallback your_dutch_english.json)")


if __name__ == "__main__":
    main()
