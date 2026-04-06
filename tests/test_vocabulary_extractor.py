from __future__ import annotations

from typing import Callable, List

from src.processing.vocabulary import VocabularyExtractor


class FakeToken:
    def __init__(
        self,
        i: int,
        text: str,
        lemma: str,
        pos: str,
        dep: str,
        head: FakeToken | None = None,
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
        self._sent: FakeSentence | None = None

    @property
    def sent(self) -> FakeSentence:
        assert self._sent is not None
        return self._sent

    @sent.setter
    def sent(self, value: FakeSentence) -> None:
        self._sent = value


class FakeSentence:
    def __init__(self, tokens: List[FakeToken]) -> None:
        self._tokens = tokens

    @property
    def text(self) -> str:
        return " ".join(token.text for token in self._tokens)


class FakeDoc(list):
    def __init__(self, tokens: List[FakeToken]) -> None:
        super().__init__(tokens)
        self.sents = [FakeSentence(tokens)]
        for token in tokens:
            token.sent = self.sents[0]


def make_fake_nlp(tokens: List[FakeToken]) -> Callable[[str], FakeDoc]:
    def fake_nlp(_: str) -> FakeDoc:
        return FakeDoc(tokens)

    return fake_nlp


class StubDictionary:
    def lookup(self, lemma: str, pos: str | None = None) -> str | None:
        if lemma == "aanvallen" and pos == "VERB":
            return "to attack"
        return None


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
