"""
Vocabulary extraction from Dutch subtitle text.

Uses spaCy (nl_core_news_md) for tokenization, lemmatization, and POS tagging.
Extracts candidate vocabulary (NOUN, VERB, ADJ, ADV) and aggregates by lemma
per episode with occurrence counts and example sentences.

Includes separable verb recombination: Dutch separable verbs like "aanvallen"
(to attack) appear split in main clauses as "vallen ... aan". The recombiner
detects these via spaCy dependency parsing and dictionary validation, storing
the combined lemma (aanvallen) instead of just the base verb (vallen).
"""

from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

KEEP_POS = {"NOUN", "VERB", "ADJ", "ADV"}
MIN_LEMMA_LENGTH = 2
EXCLUDE_LEMMAS = {"journaal"}

# Particles that can form separable verbs in Dutch.
# When split: "Ze vallen gebouwen aan" → particle "aan" + verb "vallen" = "aanvallen".
SEPARABLE_PARTICLES = frozenset({
    "aan", "af", "bij", "door", "in", "mee", "na", "neer",
    "om", "op", "over", "terug", "toe", "uit", "voor", "weg",
})

# spaCy dependency labels that indicate a separable verb particle
_SVP_DEP_LABELS = frozenset({"svp", "compound:prt", "compound"})


def _get_spacy_nlp():
    """Lazy-load spaCy Dutch model."""
    import spacy

    try:
        return spacy.load("nl_core_news_md")
    except OSError:
        raise OSError(
            "Dutch spaCy model not found. Run: python -m spacy download nl_core_news_md"
        )


class SeparableVerbRecombiner:
    """
    Detects Dutch separable verbs in a spaCy Doc and returns the combined lemma.

    Uses two detection strategies:
    1. Dependency parsing: particles with dep label 'svp' / 'compound:prt'
       whose head is a verb → combine particle + verb lemma.
    2. End-of-clause heuristic: a known particle among the last few tokens
       of a sentence, paired with a verb earlier in the sentence.

    Both strategies validate the combined form against a dictionary lookup
    to avoid false positives (e.g. "op" + "lopen" → "oplopen" only if
    "oplopen" is a real word).
    """

    def __init__(self, dictionary_lookup=None):
        self._dict = dictionary_lookup

    def _is_valid_separable_verb(self, combined_lemma: str) -> bool:
        if self._dict is None:
            return False
        return self._dict.lookup(combined_lemma, pos="VERB") is not None

    def recombine(self, doc) -> Tuple[Dict[int, str], Set[int]]:
        """
        Scan a spaCy Doc for separable verbs.

        Returns:
            verb_overrides: {token.i: combined_lemma} for verbs that should
                use the combined separable form as their lemma.
            particle_indices: set of token.i for particle tokens that were
                consumed (should be skipped during vocab extraction).
        """
        verb_overrides: Dict[int, str] = {}
        particle_indices: Set[int] = set()

        # --- Strategy 1: spaCy dependency labels ---
        for token in doc:
            if token.dep_ not in _SVP_DEP_LABELS:
                continue
            particle = token.text.lower().strip()
            if particle not in SEPARABLE_PARTICLES:
                continue
            head = token.head
            if head.pos_ != "VERB":
                continue
            combined = particle + head.lemma_.lower().strip()
            if self._is_valid_separable_verb(combined):
                verb_overrides[head.i] = combined
                particle_indices.add(token.i)

        # --- Strategy 2: end-of-clause heuristic ---
        # In Dutch main clauses the separated particle lands at the end:
        #   "Daarom vallen ze Amerikaanse gebouwen aan."
        # Only fires when the particle is the LAST content token (before
        # punctuation) to avoid false positives like "loopt op straat".
        # Tokens that spaCy already identified as prepositional (dep=case/obl)
        # are excluded - those are true prepositions, not verb particles.
        _PREP_DEP_LABELS = {"case", "obl", "nmod", "advmod"}
        for sent in doc.sents:
            tokens = list(sent)
            if len(tokens) < 3:
                continue

            # Find the last content token (skip trailing punctuation/space)
            end_tok = None
            for candidate in reversed(tokens):
                if candidate.is_punct or candidate.is_space:
                    continue
                end_tok = candidate
                break

            if end_tok is None or end_tok.i in particle_indices:
                continue
            particle = end_tok.text.lower().strip()
            if particle not in SEPARABLE_PARTICLES:
                continue
            if end_tok.pos_ not in ("ADP", "ADV", "PART"):
                continue
            # Skip tokens spaCy identified as prepositional (not particles)
            if end_tok.dep_ in _PREP_DEP_LABELS:
                continue

            # Find a verb in the sentence to pair with
            for t in tokens:
                if t.pos_ != "VERB" or t.i == end_tok.i:
                    continue
                if t.i in verb_overrides:
                    continue
                combined = particle + t.lemma_.lower().strip()
                if self._is_valid_separable_verb(combined):
                    verb_overrides[t.i] = combined
                    particle_indices.add(end_tok.i)
                    break

        return verb_overrides, particle_indices


class VocabularyExtractor:
    """
    Extracts vocabulary from Dutch text using spaCy.

    Processes subtitle segments, tokenizes and lemmatizes, filters by POS,
    and returns aggregated vocabulary with counts and example sentences.
    Optionally recombines separable verbs when a dictionary is available.
    """

    def __init__(self, nlp=None, dictionary_lookup=None):
        """
        Args:
            nlp: Optional pre-loaded spaCy Language object. If None, loads nl_core_news_md.
            dictionary_lookup: Optional DictionaryLookup instance. When provided,
                enables separable verb recombination (e.g. "vallen" + "aan" → "aanvallen").
        """
        self.nlp = nlp or _get_spacy_nlp()
        self._recombiner = SeparableVerbRecombiner(dictionary_lookup) if dictionary_lookup else None

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

            # Detect separable verbs (if dictionary available)
            verb_overrides: Dict[int, str] = {}
            particle_indices: Set[int] = set()
            if self._recombiner:
                verb_overrides, particle_indices = self._recombiner.recombine(doc)

            for token in doc:
                if token.i in particle_indices:
                    continue

                if not self._keep_token(token):
                    continue

                lemma = verb_overrides.get(token.i, token.lemma_.lower().strip())
                if len(lemma) < MIN_LEMMA_LENGTH:
                    continue
                if lemma in EXCLUDE_LEMMAS:
                    continue

                entry = vocabulary[lemma]
                entry["pos"] = token.pos_
                entry["count"] += 1
                entry["surface_forms"].add(token.text)
                if not entry["example_sentence"]:
                    entry["example_sentence"] = token.sent.text.strip()
                    entry["example_timestamp"] = timestamp

        for entry in vocabulary.values():
            entry["surface_forms"] = sorted(entry["surface_forms"])

        return dict(vocabulary)

    def _keep_token(self, token) -> bool:
        """Filter tokens: keep content words, drop stopwords/punct/names/numbers."""
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
        if token.pos_ == "PROPN":
            return False
        return True

    def extract_from_text(self, text: str) -> Dict[str, Dict]:
        """Convenience method: extract vocabulary from a single text string."""
        segments = [{"text": text, "start": None}]
        return self.extract_from_segments(segments)
