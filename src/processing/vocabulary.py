"""
Vocabulary extraction from Dutch subtitle text.

Uses spaCy (nl_core_news_md) for tokenization, lemmatization, and POS tagging.
Extracts candidate vocabulary (NOUN, VERB, ADJ, ADV) and aggregates by lemma
per episode with occurrence counts and example sentences.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# POS tags we keep for vocabulary (content words, not function words)
KEEP_POS = {"NOUN", "VERB", "ADJ", "ADV"}

# Minimum character length for a lemma (filters single chars, abbreviations)
MIN_LEMMA_LENGTH = 2

# Lemmas to exclude (part of show/program names, not useful for learning)
EXCLUDE_LEMMAS = {"journaal"}  # "NOS Journaal in Makkelijke Taal"


def _get_spacy_nlp():
    """
    Lazy-load spaCy Dutch model to avoid import-time download.

    Returns:
        spaCy Language object (nl_core_news_md).
    """
    import spacy

    try:
        return spacy.load("nl_core_news_md")
    except OSError:
        raise OSError(
            "Dutch spaCy model not found. Run: python -m spacy download nl_core_news_md"
        )


class VocabularyExtractor:
    """
    Extracts vocabulary from Dutch text using spaCy.

    Processes subtitle segments, tokenizes and lemmatizes, filters by POS,
    and returns aggregated vocabulary with counts and example sentences.
    """

    def __init__(self, nlp=None):
        """
        Initialize the extractor.

        Args:
            nlp: Optional pre-loaded spaCy Language object. If None, loads nl_core_news_md.
        """
        self.nlp = nlp or _get_spacy_nlp()

    def extract_from_segments(
        self,
        segments: List[Dict],
        segment_key: str = "text",
    ) -> Dict[str, Dict]:
        """
        Extract vocabulary from a list of subtitle segments.

        Args:
            segments: List of dicts with at least 'text' (or segment_key). Optional: 'start'.
            segment_key: Key in each segment dict containing the text to process.

        Returns:
            Dict mapping lemma -> {
                'pos': str,
                'count': int,
                'example_sentence': str,
                'example_timestamp': float | None,
                'surface_forms': set of str (word forms seen, e.g. gaan, gaat, ging),
            }
        """
        vocabulary: Dict[str, Dict] = defaultdict(
            lambda: {
                "pos": "",
                "count": 0,
                "example_sentence": "",
                "example_timestamp": None,
                "surface_forms": set(),
            }
        )

        for seg in segments:
            text = seg.get(segment_key, "")
            if not text or not text.strip():
                continue

            timestamp = seg.get("start") if "start" in seg else None

            doc = self.nlp(text)
            for token in doc:
                if not self._keep_token(token):
                    continue

                lemma = token.lemma_.lower().strip()
                if len(lemma) < MIN_LEMMA_LENGTH:
                    continue
                if lemma in EXCLUDE_LEMMAS:
                    continue

                entry = vocabulary[lemma]
                entry["pos"] = token.pos_
                entry["count"] += 1
                entry["surface_forms"].add(token.text)
                # Store first occurrence as example (could refine to pick "best" later)
                if not entry["example_sentence"]:
                    entry["example_sentence"] = token.sent.text.strip()
                    entry["example_timestamp"] = timestamp

        # Convert surface_forms set to sorted list for consistent output
        for entry in vocabulary.values():
            entry["surface_forms"] = sorted(entry["surface_forms"])

        return dict(vocabulary)

    def _keep_token(self, token) -> bool:
        """
        Filter tokens: keep content words, drop stopwords/punct/names/numbers.

        Args:
            token: spaCy Token.

        Returns:
            True if token should be included in vocabulary.
        """
        if token.pos_ not in KEEP_POS:
            return False
        if token.is_stop:
            return False
        if token.is_punct:
            return False
        if token.is_digit or token.like_num:
            return False
        if token.is_space:
            return False
        # Skip proper nouns (names, places) — usually not useful for general vocabulary
        if token.pos_ == "PROPN":
            return False
        return True

    def extract_from_text(self, text: str) -> Dict[str, Dict]:
        """
        Extract vocabulary from a single text string.

        Convenience method for full transcript text.

        Args:
            text: Raw Dutch text (e.g. concatenated subtitles).

        Returns:
            Same format as extract_from_segments.
        """
        segments = [{"text": text, "start": None}]
        return self.extract_from_segments(segments)
