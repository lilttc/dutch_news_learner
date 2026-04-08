"""
Tests for scripts/enrich_vocabulary.py - enrich_items().

Key regression guard: enrich_items() must set item.translation to
gloss_en (English), never to gloss (Dutch). Confusing the two was
the root cause of Dutch definitions appearing in the English field.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from scripts.enrich_vocabulary import enrich_items


def _item(lemma, pos, translation=None):
    """Minimal VocabularyItem stand-in."""
    obj = SimpleNamespace(lemma=lemma, pos=pos, translation=translation)
    return obj


def _lookup(entries):
    """
    Return a mock DictionaryLookup whose lookup_with_example() resolves
    from a dict keyed by lemma. Missing lemma → returns None.
    """
    mock = MagicMock()
    mock.lookup_with_example.side_effect = lambda lemma, pos=None: entries.get(lemma)
    return mock


# ---------------------------------------------------------------------------
# Core regression guard: gloss_en (English) must be used, not gloss (Dutch)
# ---------------------------------------------------------------------------

def test_translation_set_to_gloss_en() -> None:
    """item.translation is set to gloss_en, not to gloss."""
    item = _item("houden", "VERB")
    lookup = _lookup({
        "houden": {
            "gloss": "niet laten varen, het bezit ervan niet verliezen",
            "gloss_en": "to keep, preserve",
        }
    })
    enrich_items([item], lookup)
    assert item.translation == "to keep, preserve"


def test_gloss_dutch_never_written_to_translation() -> None:
    """Even if gloss (Dutch) is present, it must never end up in translation."""
    item = _item("houden", "VERB")
    lookup = _lookup({
        "houden": {
            "gloss": "niet laten varen, het bezit ervan niet verliezen",
            "gloss_en": "to keep, preserve",
        }
    })
    enrich_items([item], lookup)
    assert item.translation != "niet laten varen, het bezit ervan niet verliezen"


def test_no_gloss_en_means_no_update() -> None:
    """If the entry has no gloss_en key, item.translation is left unchanged."""
    item = _item("houden", "VERB", translation=None)
    lookup = _lookup({
        "houden": {"gloss": "niet laten varen"}  # no gloss_en
    })
    enrich_items([item], lookup)
    assert item.translation is None


# ---------------------------------------------------------------------------
# Dry-run behaviour
# ---------------------------------------------------------------------------

def test_dry_run_does_not_modify_translation() -> None:
    """dry_run=True → item.translation is never written."""
    item = _item("gaan", "VERB", translation=None)
    lookup = _lookup({"gaan": {"gloss": "bewegen", "gloss_en": "to go"}})
    enrich_items([item], lookup, dry_run=True)
    assert item.translation is None


def test_dry_run_still_counts_as_updated() -> None:
    """Dry-run counts the would-be update even without writing."""
    item = _item("gaan", "VERB")
    lookup = _lookup({"gaan": {"gloss": "bewegen", "gloss_en": "to go"}})
    updated, _ = enrich_items([item], lookup, dry_run=True)
    assert updated == 1


# ---------------------------------------------------------------------------
# Return value counts
# ---------------------------------------------------------------------------

def test_counts_updated_and_not_found() -> None:
    items = [
        _item("gaan", "VERB"),
        _item("xyzunknown", "NOUN"),
    ]
    lookup = _lookup({"gaan": {"gloss": "bewegen", "gloss_en": "to go"}})
    updated, not_found = enrich_items(items, lookup)
    assert updated == 1
    assert not_found == 1


def test_not_found_when_lookup_returns_none() -> None:
    item = _item("xyzunknown", "NOUN")
    lookup = _lookup({})  # nothing in dictionary
    updated, not_found = enrich_items([item], lookup)
    assert updated == 0
    assert not_found == 1


def test_empty_items_returns_zero_counts() -> None:
    lookup = _lookup({})
    updated, not_found = enrich_items([], lookup)
    assert updated == 0
    assert not_found == 0


# ---------------------------------------------------------------------------
# Overwrite behaviour (--all mode: caller passes all items, not just missing)
# ---------------------------------------------------------------------------

def test_existing_translation_is_overwritten() -> None:
    """When caller passes an item that already has a translation, enrich_items overwrites it."""
    item = _item("gaan", "VERB", translation="old stale value")
    lookup = _lookup({"gaan": {"gloss": "bewegen", "gloss_en": "to go"}})
    enrich_items([item], lookup)
    assert item.translation == "to go"


def test_item_with_translation_not_updated_if_not_in_lookup() -> None:
    """If the item has a translation but the word is absent from the dictionary, keep the original."""
    item = _item("xyzunknown", "NOUN", translation="existing")
    lookup = _lookup({})
    enrich_items([item], lookup)
    assert item.translation == "existing"
