"""
Tests for src/processing/vocabulary.py - VocabularyExtractor and SeparableVerbRecombiner.

Covers:
- Token filtering: stopwords, punctuation, digits, proper nouns, short lemmas, excluded lemmas
- Aggregation: count increments across segments, surface form collection
- Example sentence: captured from first occurrence, timestamp preserved
- Separable verb recombination: dep-label strategy and end-of-clause heuristic
- POS filtering: only NOUN, VERB, ADJ, ADV kept
"""

from typing import Callable, List, Optional

from src.processing.vocabulary import (
    EXCLUDE_LEMMAS,
    MIN_LEMMA_LENGTH,
    VocabularyExtractor,
)


# ---------------------------------------------------------------------------
# Fake spaCy objects (no real model needed)
# ---------------------------------------------------------------------------


class FakeToken:
    def __init__(
        self,
        i: int,
        text: str,
        lemma: str,
        pos: str,
        dep: str,
        head: Optional["FakeToken"] = None,
        is_stop: bool = False,
        is_punct: bool = False,
        is_digit: bool = False,
        like_num: bool = False,
        is_space: bool = False,
    ) -> None:
        self.i = i
        self.text = text
        self.lemma_ = lemma
        self.pos_ = pos
        self.dep_ = dep
        self.head = head or self
        self.is_stop = is_stop
        self.is_punct = is_punct
        self.is_digit = is_digit
        self.like_num = like_num
        self.is_space = is_space
        self._sent: Optional["FakeSentence"] = None

    @property
    def sent(self) -> "FakeSentence":
        assert self._sent is not None
        return self._sent

    @sent.setter
    def sent(self, value: "FakeSentence") -> None:
        self._sent = value


class FakeSentence:
    def __init__(self, tokens: List[FakeToken], text: Optional[str] = None) -> None:
        self._tokens = tokens
        self._text = text

    def __iter__(self):
        return iter(self._tokens)

    @property
    def text(self) -> str:
        return self._text if self._text is not None else " ".join(t.text for t in self._tokens)


class FakeDoc(list):
    def __init__(self, tokens: List[FakeToken], text: Optional[str] = None) -> None:
        super().__init__(tokens)
        self.sents = [FakeSentence(tokens, text=text)]
        for token in tokens:
            token.sent = self.sents[0]


def make_fake_nlp(tokens: List[FakeToken]) -> Callable[[str], FakeDoc]:
    def fake_nlp(text: str) -> FakeDoc:
        return FakeDoc(tokens, text=text)

    return fake_nlp


class StubDictionary:
    def lookup(self, lemma: str, pos: Optional[str] = None) -> Optional[str]:
        if lemma == "aanvallen" and pos == "VERB":
            return "to attack"
        if lemma == "oplopen" and pos == "VERB":
            return "to run up"
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _noun(i, text, lemma=None, is_stop=False):
    return FakeToken(
        i=i,
        text=text,
        lemma=lemma or text.lower(),
        pos="NOUN",
        dep="obj",
        is_stop=is_stop,
    )


def _verb(i, text, lemma=None):
    return FakeToken(i=i, text=text, lemma=lemma or text.lower(), pos="VERB", dep="ROOT")


def _extractor(tokens, dictionary_lookup=None):
    return VocabularyExtractor(nlp=make_fake_nlp(tokens), dictionary_lookup=dictionary_lookup)


# ---------------------------------------------------------------------------
# Separable verb recombination (existing test preserved + extended)
# ---------------------------------------------------------------------------


def test_vocabulary_extractor_recombines_separable_verb() -> None:
    tokens = [
        FakeToken(i=0, text="Ze", lemma="zij", pos="PRON", dep="nsubj", is_stop=True),
        FakeToken(i=1, text="vallen", lemma="vallen", pos="VERB", dep="ROOT"),
        FakeToken(i=2, text="gebouwen", lemma="gebouw", pos="NOUN", dep="obj"),
        FakeToken(i=3, text="aan", lemma="aan", pos="ADP", dep="compound:prt"),
        FakeToken(i=4, text=".", lemma=".", pos="PUNCT", dep="punct", is_punct=True),
    ]
    tokens[3].head = tokens[1]

    extractor = VocabularyExtractor(
        nlp=make_fake_nlp(tokens),
        dictionary_lookup=StubDictionary(),
    )
    vocab = extractor.extract_from_text("Ze vallen gebouwen aan.")

    assert "aanvallen" in vocab
    assert vocab["aanvallen"]["pos"] == "VERB"
    assert vocab["aanvallen"]["count"] == 1
    assert vocab["aanvallen"]["example_timestamp"] is None
    assert "vallen" in vocab["aanvallen"]["surface_forms"]


def test_separable_verb_particle_not_added_separately() -> None:
    """The consumed particle (aan) must not appear as its own vocabulary entry."""
    tokens = [
        FakeToken(i=0, text="Ze", lemma="zij", pos="PRON", dep="nsubj", is_stop=True),
        FakeToken(i=1, text="vallen", lemma="vallen", pos="VERB", dep="ROOT"),
        FakeToken(i=2, text="aan", lemma="aan", pos="ADP", dep="compound:prt"),
    ]
    tokens[2].head = tokens[1]

    extractor = VocabularyExtractor(nlp=make_fake_nlp(tokens), dictionary_lookup=StubDictionary())
    vocab = extractor.extract_from_text("Ze vallen aan.")

    assert "aan" not in vocab


def test_separable_verb_not_recombined_without_dictionary() -> None:
    """Without a dictionary, no recombination - base verb is kept as-is."""
    tokens = [
        FakeToken(i=0, text="vallen", lemma="vallen", pos="VERB", dep="ROOT"),
        FakeToken(i=1, text="aan", lemma="aan", pos="ADP", dep="compound:prt"),
    ]
    tokens[1].head = tokens[0]

    extractor = VocabularyExtractor(nlp=make_fake_nlp(tokens), dictionary_lookup=None)
    vocab = extractor.extract_from_text("vallen aan.")

    assert "vallen" in vocab
    assert "aanvallen" not in vocab


# ---------------------------------------------------------------------------
# Token filtering
# ---------------------------------------------------------------------------


def test_stopwords_excluded() -> None:
    tokens = [FakeToken(i=0, text="de", lemma="de", pos="NOUN", dep="det", is_stop=True)]
    vocab = _extractor(tokens).extract_from_text("de")
    assert "de" not in vocab


def test_punctuation_excluded() -> None:
    tokens = [FakeToken(i=0, text=".", lemma=".", pos="PUNCT", dep="punct", is_punct=True)]
    vocab = _extractor(tokens).extract_from_text(".")
    assert "." not in vocab


def test_digits_excluded() -> None:
    tokens = [FakeToken(i=0, text="42", lemma="42", pos="NUM", dep="nummod", is_digit=True)]
    vocab = _extractor(tokens).extract_from_text("42")
    assert "42" not in vocab


def test_like_num_excluded() -> None:
    tokens = [FakeToken(i=0, text="drie", lemma="drie", pos="NOUN", dep="obj", like_num=True)]
    vocab = _extractor(tokens).extract_from_text("drie")
    assert "drie" not in vocab


def test_propn_excluded() -> None:
    tokens = [FakeToken(i=0, text="Amsterdam", lemma="amsterdam", pos="PROPN", dep="nsubj")]
    vocab = _extractor(tokens).extract_from_text("Amsterdam")
    assert "amsterdam" not in vocab


def test_non_content_pos_excluded() -> None:
    """ADP, DET, PRON etc. are not in KEEP_POS - must be filtered out."""
    tokens = [FakeToken(i=0, text="in", lemma="in", pos="ADP", dep="case")]
    vocab = _extractor(tokens).extract_from_text("in")
    assert "in" not in vocab


def test_short_lemma_excluded() -> None:
    """Lemmas shorter than MIN_LEMMA_LENGTH must not appear."""
    tokens = [FakeToken(i=0, text="X", lemma="x", pos="NOUN", dep="obj")]
    vocab = _extractor(tokens).extract_from_text("X")
    assert "x" not in vocab
    assert MIN_LEMMA_LENGTH == 2  # keep this tied to the constant


def test_excluded_lemma_filtered_out() -> None:
    """EXCLUDE_LEMMAS entries (e.g. 'journaal') must never appear in output."""
    excluded = next(iter(EXCLUDE_LEMMAS))  # grab one entry from the set
    tokens = [FakeToken(i=0, text=excluded, lemma=excluded, pos="NOUN", dep="obj")]
    vocab = _extractor(tokens).extract_from_text(excluded)
    assert excluded not in vocab


# ---------------------------------------------------------------------------
# Aggregation: counts and surface forms
# ---------------------------------------------------------------------------


def test_count_increments_across_segments() -> None:
    """Same lemma appearing in two segments - count must be 2."""
    tokens = [_noun(0, "gebouw")]

    extractor = _extractor(tokens)
    segments = [{"text": "een gebouw"}, {"text": "het gebouw"}]
    vocab = extractor.extract_from_segments(segments)

    assert vocab["gebouw"]["count"] == 2


def test_surface_forms_collected_across_segments() -> None:
    """Different surface forms of the same lemma are all recorded."""
    calls = iter(
        [
            FakeDoc([_noun(0, "gebouwen", "gebouw")]),
            FakeDoc([_noun(0, "gebouw", "gebouw")]),
        ]
    )

    def multi_nlp(text: str):
        doc = next(calls)
        doc.sents = [FakeSentence(list(doc), text=text)]
        for tok in doc:
            tok.sent = doc.sents[0]
        return doc

    extractor = VocabularyExtractor(nlp=multi_nlp)
    vocab = extractor.extract_from_segments([{"text": "gebouwen"}, {"text": "gebouw"}])

    assert "gebouwen" in vocab["gebouw"]["surface_forms"]
    assert "gebouw" in vocab["gebouw"]["surface_forms"]


def test_multiple_distinct_lemmas_all_present() -> None:
    tokens = [_noun(0, "gebouw"), _verb(1, "lopen")]
    vocab = _extractor(tokens).extract_from_text("gebouw lopen")
    assert "gebouw" in vocab
    assert "lopen" in vocab


# ---------------------------------------------------------------------------
# Example sentence and timestamp
# ---------------------------------------------------------------------------


def test_example_sentence_captured_from_first_segment() -> None:
    tokens = [_noun(0, "gebouw")]
    vocab = _extractor(tokens).extract_from_segments([{"text": "Het grote gebouw"}])
    assert vocab["gebouw"]["example_sentence"] == "Het grote gebouw"


def test_example_timestamp_from_first_segment() -> None:
    tokens = [_noun(0, "gebouw")]
    extractor = _extractor(tokens)
    vocab = extractor.extract_from_segments([{"text": "een gebouw", "start": 12.5}])
    assert vocab["gebouw"]["example_timestamp"] == 12.5


def test_example_not_overwritten_by_later_segment() -> None:
    """Once an example sentence is set, later occurrences must not replace it."""
    calls = iter(
        [
            FakeDoc([_noun(0, "gebouw")]),
            FakeDoc([_noun(0, "gebouw")]),
        ]
    )

    def multi_nlp(text: str):
        doc = next(calls)
        doc.sents = [FakeSentence(list(doc), text=text)]
        for tok in doc:
            tok.sent = doc.sents[0]
        return doc

    extractor = VocabularyExtractor(nlp=multi_nlp)
    vocab = extractor.extract_from_segments(
        [
            {"text": "eerste gebouw", "start": 1.0},
            {"text": "tweede gebouw", "start": 2.0},
        ]
    )
    assert vocab["gebouw"]["example_sentence"] == "eerste gebouw"
    assert vocab["gebouw"]["example_timestamp"] == 1.0


def test_empty_segments_ignored() -> None:
    tokens = [_noun(0, "gebouw")]
    extractor = _extractor(tokens)
    vocab = extractor.extract_from_segments([{"text": ""}, {"text": "   "}])
    assert len(vocab) == 0
