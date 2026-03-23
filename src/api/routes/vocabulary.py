"""User vocabulary status endpoints."""

import csv
from datetime import datetime
from io import StringIO
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.dictionary.lookup import DictionaryLookup
from src.models import Episode, EpisodeVocabulary, UserVocabulary, VocabularyItem

from ..deps import get_db, get_dictionary
from ..session import get_user_id

router = APIRouter(tags=["vocabulary"])

VALID_STATUSES = {"new", "learning", "known"}

# Learner-written note per word (export / Anki); empty / null stored as NULL
USER_SENTENCE_MAX_LEN = 2000

# Export: allowed column keys (order preserved from client `columns` param)
EXPORT_COLUMN_KEYS = frozenset({
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
})

DEFAULT_EXPORT_COLUMNS = (
    "lemma",
    "pos",
    "status",
    "meaning_nl",
    "meaning_en",
    "example_episode",
    "user_sentence",
)


def _parse_export_columns(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return list(DEFAULT_EXPORT_COLUMNS)
    parts = [p.strip() for p in raw.split(",")]
    parts = [p for p in parts if p]
    invalid = [p for p in parts if p not in EXPORT_COLUMN_KEYS]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown column(s): {', '.join(invalid)}. "
                f"Allowed: {', '.join(sorted(EXPORT_COLUMN_KEYS))}"
            ),
        )
    return parts


def _published_at_key(ep: Episode) -> datetime:
    return ep.published_at if ep.published_at is not None else datetime.min


def _best_episode_examples(
    db: Session, vocabulary_ids: list[int]
) -> dict[int, dict[str, Any]]:
    """
    One example per vocabulary_id: episode with latest published_at.

    Ties keep an arbitrary row; NULL published_at sorts as oldest.
    """
    if not vocabulary_ids:
        return {}
    rows = (
        db.query(EpisodeVocabulary, Episode)
        .join(Episode, Episode.id == EpisodeVocabulary.episode_id)
        .filter(EpisodeVocabulary.vocabulary_id.in_(vocabulary_ids))
        .all()
    )
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


def _build_export_rows(
    db: Session,
    dictionary: DictionaryLookup,
    user_id: int,
    status_filter: str,
    has_note: bool | None,
) -> list[dict[str, Any]]:
    q = (
        db.query(UserVocabulary, VocabularyItem)
        .join(VocabularyItem, UserVocabulary.vocabulary_id == VocabularyItem.id)
        .filter(UserVocabulary.user_id == user_id)
    )
    if status_filter != "all":
        q = q.filter(UserVocabulary.status == status_filter)
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
    examples = _best_episode_examples(db, vids)

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
                "pos": vi.pos,
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


def _project_columns(row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    return {k: row.get(k) for k in columns}


def _anki_row(full: dict[str, Any]) -> dict[str, str]:
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


def _rows_to_csv(fieldnames: list[str], data: list[dict[str, Any]]) -> str:
    buf = StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in data:
        writer.writerow(
            {k: ("" if row.get(k) is None else row[k]) for k in fieldnames}
        )
    return buf.getvalue()


class VocabStatusUpdate(BaseModel):
    status: str


class VocabStatusOut(BaseModel):
    vocabulary_id: int
    lemma: str
    status: str
    user_sentence: str | None = None

    model_config = {"from_attributes": True}


class VocabNoteUpdate(BaseModel):
    """Set or clear the learner note for this word (null or whitespace-only clears)."""

    user_sentence: str | None = Field(
        ...,
        description="Note text; send null or '' to clear.",
        max_length=USER_SENTENCE_MAX_LEN,
    )

    @field_validator("user_sentence", mode="before")
    @classmethod
    def normalize_sentence(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        raise TypeError("user_sentence must be a string or null")


@router.get("/vocabulary/status", response_model=list[VocabStatusOut])
def list_vocab_statuses(
    status: str | None = None,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id),
):
    """
    List all vocabulary items with their user status.

    User is resolved from X-Session-Token header (or token query param).
    Without token, returns legacy shared user (user_id=1).
    """
    query = (
        db.query(UserVocabulary, VocabularyItem)
        .join(VocabularyItem, UserVocabulary.vocabulary_id == VocabularyItem.id)
        .filter(UserVocabulary.user_id == user_id)
    )
    if status:
        query = query.filter(UserVocabulary.status == status)

    return [
        VocabStatusOut(
            vocabulary_id=uv.vocabulary_id,
            lemma=vi.lemma,
            status=uv.status,
            user_sentence=uv.user_sentence,
        )
        for uv, vi in query.all()
    ]


@router.get("/vocabulary/export")
def export_vocabulary(
    status: str = Query(
        "all",
        description="Filter: new | learning | known | all",
    ),
    has_note: bool | None = Query(
        None,
        description="True = only words with a learner note; False = only without; omit = no filter",
    ),
    export_format: Literal["csv", "json"] = Query(
        "csv",
        alias="format",
        description="csv or json",
    ),
    columns: str | None = Query(
        None,
        description=(
            "Comma-separated columns (ignored if template=anki). "
            f"Default: {','.join(DEFAULT_EXPORT_COLUMNS)}"
        ),
    ),
    template: Literal["default", "anki"] = Query(
        "default",
        description="anki: fixed Front (lemma), Back (meanings + example + note), Tags",
    ),
    db: Session = Depends(get_db),
    dictionary: DictionaryLookup = Depends(get_dictionary),
    user_id: int = Depends(get_user_id),
):
    """
    Export the current user's vocabulary for spreadsheets or Anki import.

    **Episode example:** For each word, one row from `episode_vocabulary` is chosen:
    the episode with the **latest** `published_at` (ties arbitrary; NULL dates sort last).

    Auth: same as other vocabulary routes (Bearer, X-Session-Token, or legacy user).
    """
    if status not in VALID_STATUSES and status != "all":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Use: all, {', '.join(sorted(VALID_STATUSES))}",
        )

    full_rows = _build_export_rows(db, dictionary, user_id, status, has_note)

    if export_format == "json":
        if template == "anki":
            return [_anki_row(r) for r in full_rows]
        cols = _parse_export_columns(columns)
        return [_project_columns(r, cols) for r in full_rows]

    # CSV
    if template == "anki":
        anki_data = [_anki_row(r) for r in full_rows]
        csv_body = _rows_to_csv(["Front", "Back", "Tags"], anki_data)
    else:
        cols = _parse_export_columns(columns)
        projected = [_project_columns(r, cols) for r in full_rows]
        csv_body = _rows_to_csv(cols, projected)

    return Response(
        content=("\ufeff" + csv_body).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="vocabulary_export.csv"',
        },
    )


@router.put("/vocabulary/{vocabulary_id}/status", response_model=VocabStatusOut)
def update_vocab_status(
    vocabulary_id: int,
    body: VocabStatusUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id),
):
    """
    Set a word's learning status (new, learning, known).

    User is resolved from X-Session-Token header (or token query param).
    Without token, uses legacy shared user (user_id=1).
    """
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
        )

    vocab = db.query(VocabularyItem).get(vocabulary_id)
    if not vocab:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")

    row = (
        db.query(UserVocabulary)
        .filter_by(user_id=user_id, vocabulary_id=vocabulary_id)
        .first()
    )
    if row:
        row.status = body.status
    else:
        row = UserVocabulary(
            user_id=user_id, vocabulary_id=vocabulary_id, status=body.status
        )
        db.add(row)
    db.commit()

    return VocabStatusOut(
        vocabulary_id=vocabulary_id,
        lemma=vocab.lemma,
        status=body.status,
        user_sentence=row.user_sentence,
    )


@router.patch("/vocabulary/{vocabulary_id}/note", response_model=VocabStatusOut)
def update_vocab_note(
    vocabulary_id: int,
    body: VocabNoteUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id),
):
    """
    Set or clear the learner note (example sentence) for a vocabulary item.

    User is resolved from Bearer token, X-Session-Token, or legacy user_id=1.
    Only rows owned by that user are updated; vocabulary_id must exist.
    """
    vocab = db.query(VocabularyItem).get(vocabulary_id)
    if not vocab:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")

    row = (
        db.query(UserVocabulary)
        .filter_by(user_id=user_id, vocabulary_id=vocabulary_id)
        .first()
    )
    if row:
        row.user_sentence = body.user_sentence
    else:
        row = UserVocabulary(
            user_id=user_id,
            vocabulary_id=vocabulary_id,
            status="new",
            user_sentence=body.user_sentence,
        )
        db.add(row)
    db.commit()
    db.refresh(row)

    return VocabStatusOut(
        vocabulary_id=vocabulary_id,
        lemma=vocab.lemma,
        status=row.status,
        user_sentence=row.user_sentence,
    )
