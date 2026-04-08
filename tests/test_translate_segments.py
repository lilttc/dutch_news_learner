"""
Tests for translate_segments.translate_batch response parsing.

All tests mock the OpenAI client so no API calls are made.
The parsing logic (numbered vs unnumbered, blank lines, padding) is what
caused a real production bug - these tests are regression guards.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from scripts.translate_segments import translate_batch


def _make_client(response_text: str) -> MagicMock:
    """Return a mock OpenAI client that returns response_text as the LLM output."""
    message = SimpleNamespace(content=response_text)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(choices=[choice])
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


# ---------------------------------------------------------------------------
# Numbered response (model echoes "1. ...", "2. ..." format)
# ---------------------------------------------------------------------------


def test_numbered_response_correct_order() -> None:
    client = _make_client("1. Hello\n2. The world\n3. Good morning")
    result = translate_batch(client, ["Hallo", "De wereld", "Goedemorgen"])
    assert result == ["Hello", "The world", "Good morning"]


def test_numbered_response_with_blank_lines_no_shift() -> None:
    """Blank lines between numbered entries must not shift translations - this was the production bug."""  # noqa: E501
    client = _make_client("1. Hello\n\n2. The world\n\n3. Good morning")
    result = translate_batch(client, ["Hallo", "De wereld", "Goedemorgen"])
    assert result == ["Hello", "The world", "Good morning"]


def test_numbered_response_missing_entry_padded_with_empty() -> None:
    """If model skips a number, the missing position gets an empty string."""
    client = _make_client("1. Hello\n3. Good morning")
    result = translate_batch(client, ["Hallo", "De wereld", "Goedemorgen"])
    assert result == ["Hello", "", "Good morning"]


def test_numbered_response_extra_entries_truncated() -> None:
    """Model returns more items than input - truncate to input length."""
    client = _make_client("1. Hello\n2. The world\n3. Good morning\n4. Extra")
    result = translate_batch(client, ["Hallo", "De wereld", "Goedemorgen"])
    assert len(result) == 3
    assert result == ["Hello", "The world", "Good morning"]


# ---------------------------------------------------------------------------
# Unnumbered response (model ignores numbering instruction)
# ---------------------------------------------------------------------------


def test_unnumbered_response_correct_order() -> None:
    client = _make_client("Hello\nThe world\nGood morning")
    result = translate_batch(client, ["Hallo", "De wereld", "Goedemorgen"])
    assert result == ["Hello", "The world", "Good morning"]


def test_unnumbered_response_shorter_than_input_padded() -> None:
    """Fewer translations than inputs - pad with empty strings."""
    client = _make_client("Hello\nThe world")
    result = translate_batch(client, ["Hallo", "De wereld", "Goedemorgen"])
    assert result == ["Hello", "The world", ""]


def test_unnumbered_response_blank_lines_skipped() -> None:
    client = _make_client("Hello\n\nThe world\n\nGood morning")
    result = translate_batch(client, ["Hallo", "De wereld", "Goedemorgen"])
    assert result == ["Hello", "The world", "Good morning"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_single_item_batch() -> None:
    client = _make_client("1. Hello")
    result = translate_batch(client, ["Hallo"])
    assert result == ["Hello"]


def test_output_length_always_matches_input() -> None:
    """Result must always have the same length as the input list."""
    inputs = [f"zin {i}" for i in range(12)]
    client = _make_client("1. one\n2. two")  # deliberately short
    result = translate_batch(client, inputs)
    assert len(result) == len(inputs)
