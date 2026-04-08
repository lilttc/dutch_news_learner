"""
Tests for scripts/enrich_vocab_llm.py - _build_prompt and enrich_batch.

Covers:
- _build_prompt: lemma/POS/example formatting, missing example omitted, numbering
- enrich_batch: valid JSON parsing, markdown fence stripping, short-response
  padding with None, long-response truncation, all-None fallback on bad JSON,
  empty/whitespace strings treated as None
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from scripts.enrich_vocab_llm import _build_prompt, enrich_batch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _word(lemma="gaan", pos="VERB", example="Ik ga naar school."):
    return {"lemma": lemma, "pos": pos, "example": example}


def _make_client(response_text: str) -> MagicMock:
    message = SimpleNamespace(content=response_text)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(choices=[choice])
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_includes_lemma_and_pos() -> None:
    prompt = _build_prompt([_word("gaan", "VERB")])
    assert "gaan" in prompt
    assert "VERB" in prompt


def test_build_prompt_includes_example() -> None:
    prompt = _build_prompt([_word(example="Ik ga naar school.")])
    assert "Ik ga naar school." in prompt


def test_build_prompt_omits_example_when_empty() -> None:
    prompt = _build_prompt([_word(example="")])
    assert "Example:" not in prompt


def test_build_prompt_numbers_entries() -> None:
    prompt = _build_prompt([_word("gaan"), _word("houden")])
    assert "1." in prompt
    assert "2." in prompt


def test_build_prompt_multiple_words_all_present() -> None:
    words = [_word("gaan", "VERB"), _word("huis", "NOUN"), _word("groot", "ADJ")]
    prompt = _build_prompt(words)
    for w in words:
        assert w["lemma"] in prompt


# ---------------------------------------------------------------------------
# enrich_batch - JSON parsing
# ---------------------------------------------------------------------------

def test_enrich_batch_parses_valid_json_array() -> None:
    client = _make_client(json.dumps(["to go", "house"]))
    result = enrich_batch(client, [_word("gaan"), _word("huis", "NOUN")])
    assert result == ["to go", "house"]


def test_enrich_batch_strips_markdown_fences() -> None:
    payload = json.dumps(["to go"])
    client = _make_client(f"```json\n{payload}\n```")
    result = enrich_batch(client, [_word("gaan")])
    assert result == ["to go"]


def test_enrich_batch_strips_plain_code_fences() -> None:
    payload = json.dumps(["to go"])
    client = _make_client(f"```\n{payload}\n```")
    result = enrich_batch(client, [_word("gaan")])
    assert result == ["to go"]


# ---------------------------------------------------------------------------
# enrich_batch - length normalisation
# ---------------------------------------------------------------------------

def test_enrich_batch_pads_short_response_with_none() -> None:
    """Model returns fewer items than input - missing positions get None."""
    client = _make_client(json.dumps(["to go"]))
    result = enrich_batch(client, [_word("gaan"), _word("huis", "NOUN"), _word("groot", "ADJ")])
    assert len(result) == 3
    assert result[0] == "to go"
    assert result[1] is None
    assert result[2] is None


def test_enrich_batch_truncates_long_response() -> None:
    """Model returns more items than input - truncate to input length."""
    client = _make_client(json.dumps(["to go", "house", "big", "extra"]))
    result = enrich_batch(client, [_word("gaan"), _word("huis", "NOUN")])
    assert len(result) == 2
    assert result == ["to go", "house"]


def test_enrich_batch_output_length_always_matches_input() -> None:
    words = [_word() for _ in range(7)]
    client = _make_client(json.dumps(["to go", "house"]))  # deliberately short
    result = enrich_batch(client, words)
    assert len(result) == 7


# ---------------------------------------------------------------------------
# enrich_batch - invalid/empty values
# ---------------------------------------------------------------------------

def test_enrich_batch_empty_string_becomes_none() -> None:
    client = _make_client(json.dumps(["to go", "", "big"]))
    result = enrich_batch(client, [_word("gaan"), _word("huis", "NOUN"), _word("groot", "ADJ")])
    assert result[0] == "to go"
    assert result[1] is None
    assert result[2] == "big"


def test_enrich_batch_whitespace_only_string_becomes_none() -> None:
    client = _make_client(json.dumps(["to go", "   "]))
    result = enrich_batch(client, [_word("gaan"), _word("huis", "NOUN")])
    assert result[1] is None


def test_enrich_batch_returns_all_none_on_invalid_json() -> None:
    """Unparseable response - return all None, no exception raised."""
    client = _make_client("this is not json")
    result = enrich_batch(client, [_word("gaan"), _word("huis", "NOUN")])
    assert result == [None, None]
