"""
Processing module — NLP pipeline for vocabulary extraction.

Extracts lemmas from subtitle text using spaCy, filters by POS,
and aggregates vocabulary per episode.
"""

from .vocabulary import VocabularyExtractor

__all__ = ["VocabularyExtractor"]
