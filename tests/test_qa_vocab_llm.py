"""
Tests for scripts/qa_vocab_llm.py.

Covers:
- _build_prompt: word block formatting, missing translation sentinel
- _qa_batch: JSON parsing, markdown fence stripping, short-response padding, failure fallback
- _apply_qa_result: echo detection, translation write, MWE flagging, null passthrough
- _log_eval: JSONL line written with correct fields
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts.qa_vocab_llm import _apply_qa_result, _build_prompt, _log_eval, _qa_batch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _word(lemma="gaan", pos="VERB", translation="to go", example="Ik ga naar school."):
    return {"lemma": lemma, "pos": pos, "translation": translation, "example": example}


def _make_client(response_text: str) -> MagicMock:
    message = SimpleNamespace(content=response_text)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(choices=[choice])
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


def _vocab_item():
    return SimpleNamespace(qa_translation=None, qa_note=None, qa_checked=False)


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


def test_build_prompt_includes_lemma_pos_translation() -> None:
    words = [_word("gaan", "VERB", "to go", "")]
    prompt = _build_prompt(words)
    assert '"gaan"' in prompt
    assert "VERB" in prompt
    assert '"to go"' in prompt


def test_build_prompt_includes_example_sentence() -> None:
    words = [_word(example="Ik ga naar school.")]
    prompt = _build_prompt(words)
    assert "Ik ga naar school." in prompt


def test_build_prompt_missing_translation_uses_sentinel() -> None:
    """Empty translation must show 'no translation available', not an empty string."""
    words = [_word(translation="")]
    prompt = _build_prompt(words)
    assert "no translation available" in prompt


def test_build_prompt_none_translation_uses_sentinel() -> None:
    words = [_word(translation=None)]
    prompt = _build_prompt(words)
    assert "no translation available" in prompt


def test_build_prompt_numbers_entries() -> None:
    words = [_word("gaan"), _word("houden")]
    prompt = _build_prompt(words)
    assert "1." in prompt
    assert "2." in prompt


def test_build_prompt_no_example_skips_example_line() -> None:
    words = [_word(example="")]
    prompt = _build_prompt(words)
    assert "Example:" not in prompt


# ---------------------------------------------------------------------------
# _qa_batch - JSON parsing
# ---------------------------------------------------------------------------


def test_qa_batch_parses_valid_json() -> None:
    response = json.dumps(
        [{"corrected_pos": None, "corrected_translation": "to go", "mwe_note": None}]
    )
    client = _make_client(response)
    results = _qa_batch(client, [_word()], model="gpt-4o")
    assert results[0]["corrected_translation"] == "to go"


def test_qa_batch_strips_markdown_fences() -> None:
    payload = json.dumps(
        [{"corrected_pos": None, "corrected_translation": "to go", "mwe_note": None}]
    )
    response = f"```json\n{payload}\n```"
    client = _make_client(response)
    results = _qa_batch(client, [_word()], model="gpt-4o")
    assert results[0]["corrected_translation"] == "to go"


def test_qa_batch_pads_short_response() -> None:
    """Model returns fewer items than input - pad with empty dicts."""
    words = [_word("gaan"), _word("houden"), _word("zijn")]
    response = json.dumps(
        [{"corrected_pos": None, "corrected_translation": "to go", "mwe_note": None}]
    )
    client = _make_client(response)
    results = _qa_batch(client, words, model="gpt-4o")
    assert len(results) == 3
    assert results[1]["corrected_translation"] is None
    assert results[2]["corrected_translation"] is None


def test_qa_batch_returns_empty_dicts_on_invalid_json() -> None:
    """Unparseable response - return all-null fallback, no exception raised."""
    client = _make_client("this is not json at all")
    words = [_word("gaan"), _word("houden")]
    results = _qa_batch(client, words, model="gpt-4o")
    assert len(results) == 2
    assert all(r["corrected_translation"] is None for r in results)


# ---------------------------------------------------------------------------
# _apply_qa_result - echo detection and write logic
# ---------------------------------------------------------------------------


def test_apply_writes_new_translation() -> None:
    item = _vocab_item()
    word = _word(translation="to keep")
    result = {"corrected_translation": "to keep, preserve", "mwe_note": None}
    changed, _ = _apply_qa_result(item, word, result)
    assert changed is True
    assert item.qa_translation == "to keep, preserve"


def test_apply_echo_detection_ignores_same_translation() -> None:
    """Model echoes back the original translation - must NOT store it as a correction."""
    item = _vocab_item()
    word = _word(translation="to go")
    result = {"corrected_translation": "to go", "mwe_note": None}
    changed, _ = _apply_qa_result(item, word, result)
    assert changed is False
    assert item.qa_translation is None


def test_apply_echo_detection_case_insensitive() -> None:
    item = _vocab_item()
    word = _word(translation="To Go")
    result = {"corrected_translation": "to go", "mwe_note": None}
    changed, _ = _apply_qa_result(item, word, result)
    assert changed is False


def test_apply_null_translation_not_written() -> None:
    item = _vocab_item()
    word = _word(translation="to go")
    result = {"corrected_translation": None, "mwe_note": None}
    changed, _ = _apply_qa_result(item, word, result)
    assert changed is False
    assert item.qa_translation is None


def test_apply_writes_mwe_note() -> None:
    item = _vocab_item()
    word = _word("slotte")
    result = {
        "corrected_translation": None,
        "mwe_note": "part of 'ten slotte' (finally)",
    }
    _, mwe = _apply_qa_result(item, word, result)
    assert mwe is True
    assert item.qa_note == "part of 'ten slotte' (finally)"


def test_apply_null_mwe_not_written() -> None:
    item = _vocab_item()
    word = _word()
    result = {"corrected_translation": None, "mwe_note": None}
    _, mwe = _apply_qa_result(item, word, result)
    assert mwe is False
    assert item.qa_note is None


def test_apply_strips_whitespace_from_translation() -> None:
    item = _vocab_item()
    word = _word(translation="to keep")
    result = {"corrected_translation": "  to keep, preserve  ", "mwe_note": None}
    _apply_qa_result(item, word, result)
    assert item.qa_translation == "to keep, preserve"


# ---------------------------------------------------------------------------
# _log_eval - JSONL output
# ---------------------------------------------------------------------------


def test_log_eval_writes_jsonl_line(tmp_path: Path) -> None:
    word = _word("gaan", "VERB", "to go", "Ik ga naar school.")
    log_path = tmp_path / "qa_vocab_eval.jsonl"

    with patch("scripts.qa_vocab_llm.EVAL_LOG", log_path):
        _log_eval(word, qa_pos=None, qa_translation="to go somewhere", qa_note=None)

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["lemma"] == "gaan"
    assert record["original_translation"] == "to go"
    assert record["qa_translation"] == "to go somewhere"
    assert record["qa_pos"] is None
    assert "ts" in record


def test_log_eval_appends_multiple_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "qa_vocab_eval.jsonl"
    word = _word()

    with patch("scripts.qa_vocab_llm.EVAL_LOG", log_path):
        _log_eval(word, qa_pos=None, qa_translation=None, qa_note=None)
        _log_eval(word, qa_pos=None, qa_translation="corrected", qa_note=None)

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
