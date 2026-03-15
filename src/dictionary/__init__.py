"""
Dictionary module — Dutch word lookup with English glosses.

Uses Kaikki Wiktionary extract (Dutch words with English definitions).
Falls back to authoritative links (Van Dale, Woorden.org) when no local match.
"""

from .lookup import DictionaryLookup, get_lookup

__all__ = ["DictionaryLookup", "get_lookup"]
