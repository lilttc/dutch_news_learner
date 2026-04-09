"""
Build vocabulary export rows for API and Streamlit (same columns as GET /vocabulary/export).
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.dictionary.lookup import DictionaryLookup
from src.models import (
    Episode,
    EpisodeVocabulary,
    UserEpisodeWatch,
    UserVocabulary,
    VocabularyItem,
)

EXPORT_COLUMN_KEYS = frozenset(
    {
        "vocabulary_id",
        "lemma",
        "pos",
        "status",
        "user_sentence",
        "meaning_nl",
        "meaning_en",
        "example_episode",
        "episode_title",
        "episode_id",
    }
)

DEFAULT_EXPORT_COLUMNS = (
    "lemma",
    "pos",
    "status",
    "meaning_nl",
    "meaning_en",
    "example_episode",
    "user_sentence",
)

# Stable order for multiselect / docs (all keys present)
ORDERED_EXPORT_COLUMNS: tuple[str, ...] = (
    "lemma",
    "pos",
    "status",
    "meaning_nl",
    "meaning_en",
    "example_episode",
    "episode_title",
    "episode_id",
    "user_sentence",
    "vocabulary_id",
)

EXPORT_COLUMN_LABELS: dict[str, str] = {
    "vocabulary_id": "Vocabulary ID",
    "lemma": "Word",
    "pos": "Word type (grammar)",
    "status": "Status",
    "user_sentence": "My sentence",
    "meaning_nl": "Meaning (NL)",
    "meaning_en": "Meaning (EN)",
    "example_episode": "Episode example",
    "episode_title": "Episode title",
    "episode_id": "Episode ID",
}

# spaCy-style POS → short English hint for learners (optional display)
POS_HINTS: dict[str, str] = {
    "NOUN": "noun",
    "VERB": "verb",
    "ADJ": "adjective",
    "ADV": "adverb",
    "PROPN": "name",
    "PRON": "pronoun",
    "ADP": "preposition",
    "DET": "determiner",
    "AUX": "auxiliary verb",
    "CONJ": "conjunction",
    "CCONJ": "conjunction",
    "SCONJ": "conjunction",
    "INTJ": "interjection",
    "NUM": "numeral",
    "PART": "particle",
    "SPACE": "-",
    "PUNCT": "punctuation",
    "SYM": "symbol",
    "X": "other",
}

EXPORT_VALID_STATUSES = frozenset({"new", "learning", "known"})

# Filter vocabulary by whether it appears in episodes the user marked watched (explicit toggle)
EPISODE_WATCH_ANY = "any"
EPISODE_WATCH_WATCHED_ONLY = "watched_only"
EPISODE_WATCH_UNWATCHED_ONLY = "unwatched_only"
EXPORT_VALID_EPISODE_WATCH = frozenset(
    {EPISODE_WATCH_ANY, EPISODE_WATCH_WATCHED_ONLY, EPISODE_WATCH_UNWATCHED_ONLY}
)


def parse_episode_watch_param(raw: str | None) -> str:
    """Normalize API query; raises ValueError if invalid."""
    s = (raw or EPISODE_WATCH_ANY).strip().lower()
    if s in ("", "all"):
        s = EPISODE_WATCH_ANY
    if s not in EXPORT_VALID_EPISODE_WATCH:
        raise ValueError(
            f"Invalid episode_watch: {raw!r}. "
            f"Use: {', '.join(sorted(EXPORT_VALID_EPISODE_WATCH))}"
        )
    return s


def format_pos_for_display(pos: str | None) -> str | None:
    """Human-friendly POS for tables (e.g. NOUN → noun)."""
    if not pos:
        return None
    p = pos.strip().upper()
    return POS_HINTS.get(p, pos)


def parse_statuses_export(status: str) -> list[str] | None:
    """
    Parse API `status` param: 'all' → None (no filter).
    Comma-separated e.g. 'new,learning' → subset.
    Raises ValueError on invalid tokens.
    """
    s = (status or "all").strip().lower()
    if s == "all":
        return None
    parts = [p.strip().lower() for p in s.split(",") if p.strip()]
    invalid = [p for p in parts if p not in EXPORT_VALID_STATUSES]
    if invalid:
        raise ValueError(
            f"Invalid status value(s): {', '.join(invalid)}. "
            f"Use 'all' or one or more of: {', '.join(sorted(EXPORT_VALID_STATUSES))}"
        )
    if not parts:
        return None
    return parts


def _vocabulary_ids_in_episode_date_range(
    db: Session,
    date_from: date | None,
    date_to: date | None,
) -> set[int] | None:
    """None = do not filter by episode date; else vocabulary_ids appearing in that window."""
    if date_from is None and date_to is None:
        return None
    q = db.query(EpisodeVocabulary.vocabulary_id).join(
        Episode, Episode.id == EpisodeVocabulary.episode_id
    )
    if date_from is not None:
        q = q.filter(func.date(Episode.published_at) >= date_from)
    if date_to is not None:
        q = q.filter(func.date(Episode.published_at) <= date_to)
    return {r[0] for r in q.distinct().all()}


def _vocabulary_ids_for_episode_watch_filter(
    db: Session, user_id: int, mode: str
) -> set[int] | None:
    """
    None = no watch filter.
    watched_only: word appears in at least one episode user marked watched.
    unwatched_only: word appears in at least one episode user has not marked watched.
    """
    if mode == EPISODE_WATCH_ANY:
        return None
    if mode == EPISODE_WATCH_WATCHED_ONLY:
        q = db.query(EpisodeVocabulary.vocabulary_id).join(
            UserEpisodeWatch,
            (UserEpisodeWatch.episode_id == EpisodeVocabulary.episode_id)
            & (UserEpisodeWatch.user_id == user_id),
        )
        return {r[0] for r in q.distinct().all()}
    if mode == EPISODE_WATCH_UNWATCHED_ONLY:
        watched_rows = (
            db.query(UserEpisodeWatch.episode_id).filter(UserEpisodeWatch.user_id == user_id).all()
        )
        watched_ids = [r[0] for r in watched_rows]
        q = db.query(EpisodeVocabulary.vocabulary_id)
        if watched_ids:
            q = q.filter(~EpisodeVocabulary.episode_id.in_(watched_ids))
        return {r[0] for r in q.distinct().all()}
    return None


def parse_export_columns(raw: str | None) -> list[str]:
    """Parse comma-separated column list; raises ValueError if unknown keys."""
    if not raw or not raw.strip():
        return list(DEFAULT_EXPORT_COLUMNS)
    parts = [p.strip() for p in raw.split(",")]
    parts = [p for p in parts if p]
    invalid = [p for p in parts if p not in EXPORT_COLUMN_KEYS]
    if invalid:
        raise ValueError(
            f"Unknown column(s): {', '.join(invalid)}. "
            f"Allowed: {', '.join(sorted(EXPORT_COLUMN_KEYS))}"
        )
    return parts


def _published_at_key(ep: Episode) -> datetime:
    return ep.published_at if ep.published_at is not None else datetime.min


def _best_episode_examples(
    db: Session,
    vocabulary_ids: list[int],
    *,
    published_from: date | None = None,
    published_to: date | None = None,
) -> dict[int, dict[str, Any]]:
    """
    One example per vocabulary_id: episode with latest published_at.

    Ties keep an arbitrary row; NULL published_at sorts as oldest.
    If published_from / published_to are set, only episodes in that date range are considered.
    """
    if not vocabulary_ids:
        return {}
    q = (
        db.query(EpisodeVocabulary, Episode)
        .join(Episode, Episode.id == EpisodeVocabulary.episode_id)
        .filter(EpisodeVocabulary.vocabulary_id.in_(vocabulary_ids))
    )
    if published_from is not None:
        q = q.filter(func.date(Episode.published_at) >= published_from)
    if published_to is not None:
        q = q.filter(func.date(Episode.published_at) <= published_to)
    rows = q.all()
    best: dict[int, tuple[EpisodeVocabulary, Episode]] = {}
    for ev, ep in rows:
        vid = ev.vocabulary_id
        if vid not in best:
            best[vid] = (ev, ep)
        else:
            old_ev, old_ep = best[vid]
            if _published_at_key(ep) > _published_at_key(old_ep):
                best[vid] = (ev, ep)
    out: dict[int, dict[str, Any]] = {}
    for vid, (ev, ep) in best.items():
        out[vid] = {
            "example_episode": ev.example_sentence,
            "episode_id": ep.id,
            "episode_title": ep.title,
        }
    return out


def build_export_rows(
    db: Session,
    dictionary: DictionaryLookup,
    user_id: int,
    statuses: list[str] | None,
    has_note: bool | None,
    *,
    episode_date_from: date | None = None,
    episode_date_to: date | None = None,
    episode_watch: str = EPISODE_WATCH_ANY,
) -> list[dict[str, Any]]:
    """
    statuses: None = all statuses; else filter to these (new / learning / known).
    has_note: True / False / None (no filter).
    episode_date_from / episode_date_to: only words that appear in at least one episode
    whose published_at date falls in the range (inclusive). Example column uses the same window.
    episode_watch: any | watched_only | unwatched_only (see _vocabulary_ids_for_episode_watch_filter).
    """
    q = (
        db.query(UserVocabulary, VocabularyItem)
        .join(VocabularyItem, UserVocabulary.vocabulary_id == VocabularyItem.id)
        .filter(UserVocabulary.user_id == user_id)
    )
    vocab_sets: list[set[int]] = []
    vids_by_date = _vocabulary_ids_in_episode_date_range(db, episode_date_from, episode_date_to)
    if vids_by_date is not None:
        vocab_sets.append(vids_by_date)
    vids_by_watch = _vocabulary_ids_for_episode_watch_filter(db, user_id, episode_watch)
    if vids_by_watch is not None:
        vocab_sets.append(vids_by_watch)
    if vocab_sets:
        combined = vocab_sets[0]
        for s in vocab_sets[1:]:
            combined = combined & s
        if not combined:
            return []
        q = q.filter(VocabularyItem.id.in_(combined))

    if statuses is not None:
        if not statuses:
            return []
        q = q.filter(UserVocabulary.status.in_(statuses))
    if has_note is True:
        q = q.filter(
            UserVocabulary.user_sentence.isnot(None),
            UserVocabulary.user_sentence != "",
        )
    elif has_note is False:
        q = q.filter(
            or_(
                UserVocabulary.user_sentence.is_(None),
                UserVocabulary.user_sentence == "",
            )
        )

    pairs = q.order_by(VocabularyItem.lemma).all()
    if not pairs:
        return []

    vids = [vi.id for _, vi in pairs]
    examples = _best_episode_examples(
        db,
        vids,
        published_from=episode_date_from,
        published_to=episode_date_to,
    )

    rows_out: list[dict[str, Any]] = []
    for uv, vi in pairs:
        entry = dictionary.lookup_with_example(vi.lemma, vi.pos)
        gloss_nl = vi.translation or (entry.get("gloss") if entry else None)
        gloss_en = entry.get("gloss_en") if entry else None
        ex = examples.get(vi.id, {})
        rows_out.append(
            {
                "vocabulary_id": vi.id,
                "lemma": vi.lemma,
                "pos": format_pos_for_display(vi.pos),
                "status": uv.status,
                "user_sentence": uv.user_sentence,
                "meaning_nl": gloss_nl,
                "meaning_en": gloss_en,
                "example_episode": ex.get("example_episode"),
                "episode_title": ex.get("episode_title"),
                "episode_id": ex.get("episode_id"),
            }
        )
    return rows_out


def project_export_columns(row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    return {k: row.get(k) for k in columns}


def build_anki_row(full: dict[str, Any]) -> dict[str, str]:
    parts: list[str] = []
    if full.get("meaning_nl"):
        parts.append(f"NL: {full['meaning_nl']}")
    if full.get("meaning_en"):
        parts.append(f"EN: {full['meaning_en']}")
    if full.get("example_episode"):
        parts.append(f"Example: {full['example_episode']}")
    if full.get("user_sentence"):
        parts.append(f"My note: {full['user_sentence']}")
    return {
        "Front": full.get("lemma") or "",
        "Back": "\n".join(parts),
        "Tags": "dutch_news_learner",
    }


def export_rows_to_csv(
    fieldnames: list[str],
    data: list[dict[str, Any]],
    *,
    header_aliases: dict[str, str] | None = None,
) -> str:
    """Write CSV rows; optional header_aliases map internal keys to human column titles."""
    buf = StringIO()
    headers = [header_aliases.get(f, f) for f in fieldnames] if header_aliases else fieldnames
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(headers)
    for row in data:
        w.writerow(["" if row.get(f) is None else row[f] for f in fieldnames])
    return buf.getvalue()
