"""
Unit tests for src/vocab_export.py - pure logic functions only.

build_export_rows and _best_episode_examples require a DB session and are
tested implicitly via the API. Here we test the pure parsing and formatting.
"""

import pytest

from src.vocab_export import (
    DEFAULT_EXPORT_COLUMNS,
    build_anki_row,
    export_rows_to_csv,
    format_pos_for_display,
    parse_episode_watch_param,
    parse_export_columns,
    parse_statuses_export,
    project_export_columns,
)


# ---------------------------------------------------------------------------
# parse_episode_watch_param
# ---------------------------------------------------------------------------


def test_parse_episode_watch_none_returns_any() -> None:
    assert parse_episode_watch_param(None) == "any"


def test_parse_episode_watch_empty_returns_any() -> None:
    assert parse_episode_watch_param("") == "any"


def test_parse_episode_watch_all_returns_any() -> None:
    assert parse_episode_watch_param("all") == "any"


def test_parse_episode_watch_valid_values() -> None:
    assert parse_episode_watch_param("watched_only") == "watched_only"
    assert parse_episode_watch_param("unwatched_only") == "unwatched_only"
    assert parse_episode_watch_param("any") == "any"


def test_parse_episode_watch_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Invalid episode_watch"):
        parse_episode_watch_param("invalid_value")


# ---------------------------------------------------------------------------
# parse_statuses_export
# ---------------------------------------------------------------------------


def test_parse_statuses_all_returns_none() -> None:
    assert parse_statuses_export("all") is None


def test_parse_statuses_empty_returns_none() -> None:
    assert parse_statuses_export("") is None


def test_parse_statuses_single() -> None:
    assert parse_statuses_export("new") == ["new"]


def test_parse_statuses_multiple() -> None:
    result = parse_statuses_export("new,learning")
    assert set(result) == {"new", "learning"}


def test_parse_statuses_all_three() -> None:
    result = parse_statuses_export("new,learning,known")
    assert set(result) == {"new", "learning", "known"}


def test_parse_statuses_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Invalid status"):
        parse_statuses_export("new,invalid")


def test_parse_statuses_strips_whitespace() -> None:
    result = parse_statuses_export(" new , learning ")
    assert set(result) == {"new", "learning"}


# ---------------------------------------------------------------------------
# parse_export_columns
# ---------------------------------------------------------------------------


def test_parse_export_columns_none_returns_defaults() -> None:
    result = parse_export_columns(None)
    assert result == list(DEFAULT_EXPORT_COLUMNS)


def test_parse_export_columns_empty_returns_defaults() -> None:
    assert parse_export_columns("") == list(DEFAULT_EXPORT_COLUMNS)


def test_parse_export_columns_valid() -> None:
    result = parse_export_columns("lemma,pos,status")
    assert result == ["lemma", "pos", "status"]


def test_parse_export_columns_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Unknown column"):
        parse_export_columns("lemma,not_a_real_column")


def test_parse_export_columns_strips_whitespace() -> None:
    result = parse_export_columns(" lemma , pos ")
    assert result == ["lemma", "pos"]


# ---------------------------------------------------------------------------
# format_pos_for_display
# ---------------------------------------------------------------------------


def test_format_pos_noun() -> None:
    assert format_pos_for_display("NOUN") == "noun"


def test_format_pos_verb() -> None:
    assert format_pos_for_display("VERB") == "verb"


def test_format_pos_none_returns_none() -> None:
    assert format_pos_for_display(None) is None


def test_format_pos_unknown_returns_original() -> None:
    assert format_pos_for_display("UNKNOWNPOS") == "UNKNOWNPOS"


def test_format_pos_case_insensitive() -> None:
    assert format_pos_for_display("noun") == "noun"


# ---------------------------------------------------------------------------
# build_anki_row
# ---------------------------------------------------------------------------


def test_build_anki_row_front_is_lemma() -> None:
    row = build_anki_row({"lemma": "gaan", "meaning_nl": None, "meaning_en": None})
    assert row["Front"] == "gaan"


def test_build_anki_row_back_contains_meanings() -> None:
    row = build_anki_row(
        {
            "lemma": "gaan",
            "meaning_nl": "bewegen",
            "meaning_en": "to go",
            "example_episode": None,
            "user_sentence": None,
        }
    )
    assert "NL: bewegen" in row["Back"]
    assert "EN: to go" in row["Back"]


def test_build_anki_row_back_contains_example() -> None:
    row = build_anki_row(
        {
            "lemma": "gaan",
            "meaning_nl": None,
            "meaning_en": None,
            "example_episode": "Ik ga naar school.",
            "user_sentence": None,
        }
    )
    assert "Example: Ik ga naar school." in row["Back"]


def test_build_anki_row_back_contains_user_sentence() -> None:
    row = build_anki_row(
        {
            "lemma": "gaan",
            "meaning_nl": None,
            "meaning_en": None,
            "example_episode": None,
            "user_sentence": "Ik ga weg.",
        }
    )
    assert "My note: Ik ga weg." in row["Back"]


def test_build_anki_row_tags() -> None:
    row = build_anki_row({"lemma": "gaan"})
    assert row["Tags"] == "dutch_news_learner"


def test_build_anki_row_missing_lemma() -> None:
    row = build_anki_row({})
    assert row["Front"] == ""


# ---------------------------------------------------------------------------
# project_export_columns
# ---------------------------------------------------------------------------


def test_project_export_columns_keeps_only_requested() -> None:
    row = {"lemma": "gaan", "pos": "VERB", "status": "new", "meaning_nl": "bewegen"}
    result = project_export_columns(row, ["lemma", "pos"])
    assert result == {"lemma": "gaan", "pos": "VERB"}


def test_project_export_columns_missing_key_is_none() -> None:
    result = project_export_columns({"lemma": "gaan"}, ["lemma", "pos"])
    assert result["pos"] is None


# ---------------------------------------------------------------------------
# export_rows_to_csv
# ---------------------------------------------------------------------------


def test_export_rows_to_csv_header_row() -> None:
    csv_str = export_rows_to_csv(["lemma", "pos"], [{"lemma": "gaan", "pos": "VERB"}])
    lines = csv_str.strip().splitlines()
    assert lines[0] == "lemma,pos"


def test_export_rows_to_csv_data_row() -> None:
    csv_str = export_rows_to_csv(["lemma", "pos"], [{"lemma": "gaan", "pos": "VERB"}])
    lines = csv_str.strip().splitlines()
    assert lines[1] == "gaan,VERB"


def test_export_rows_to_csv_none_becomes_empty() -> None:
    csv_str = export_rows_to_csv(["lemma", "pos"], [{"lemma": "gaan", "pos": None}])
    lines = csv_str.strip().splitlines()
    assert lines[1] == "gaan,"


def test_export_rows_to_csv_header_aliases() -> None:
    csv_str = export_rows_to_csv(
        ["lemma", "pos"],
        [{"lemma": "gaan", "pos": "VERB"}],
        header_aliases={"lemma": "Word", "pos": "Type"},
    )
    lines = csv_str.strip().splitlines()
    assert lines[0] == "Word,Type"
