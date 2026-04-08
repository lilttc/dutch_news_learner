"""User vocabulary status endpoints."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.dictionary.lookup import DictionaryLookup
from src.models import UserVocabulary, VocabularyItem
from src.vocab_export import (
    DEFAULT_EXPORT_COLUMNS,
    build_anki_row,
    build_export_rows,
    export_rows_to_csv,
    parse_episode_watch_param,
    parse_export_columns,
    parse_statuses_export,
    project_export_columns,
)

from ..deps import get_db, get_dictionary
from ..session import get_user_id

router = APIRouter(tags=["vocabulary"])

VALID_STATUSES = {"new", "learning", "known"}

# Learner-written note per word (export / Anki); empty / null stored as NULL
USER_SENTENCE_MAX_LEN = 2000


def _parse_export_columns_api(raw: str | None) -> list[str]:
    try:
        return parse_export_columns(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _parse_episode_watch_api(raw: str | None) -> str:
    try:
        return parse_episode_watch_param(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
        description=(
            "'all' or comma-separated subset, e.g. 'new,learning'. "
            "Each of: new, learning, known."
        ),
    ),
    has_note: bool | None = Query(
        None,
        description="True = only words with a learner note; False = only without; omit = no filter",
    ),
    episode_from: date | None = Query(
        None,
        description=(
            "Only include words that appear in an episode published on/after this date "
            "(calendar day, UTC)."
        ),
    ),
    episode_to: date | None = Query(
        None,
        description=(
            "Only include words that appear in an episode published on/before this date "
            "(calendar day, UTC)."
        ),
    ),
    episode_watch: str = Query(
        "any",
        description=(
            "any | watched_only | unwatched_only - filter by episodes you marked watched "
            "(same user_id as vocab; explicit toggle, not auto-playback)."
        ),
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
    the episode with the **latest** `published_at` among rows matching any date filter
    (ties arbitrary; NULL dates sort last).

    Auth: same as other vocabulary routes (Bearer, X-Session-Token, or legacy user).
    """
    try:
        statuses = parse_statuses_export(status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    ew = _parse_episode_watch_api(episode_watch)

    full_rows = build_export_rows(
        db,
        dictionary,
        user_id,
        statuses,
        has_note,
        episode_date_from=episode_from,
        episode_date_to=episode_to,
        episode_watch=ew,
    )

    if export_format == "json":
        if template == "anki":
            return [build_anki_row(r) for r in full_rows]
        cols = _parse_export_columns_api(columns)
        return [project_export_columns(r, cols) for r in full_rows]

    # CSV
    if template == "anki":
        anki_data = [build_anki_row(r) for r in full_rows]
        csv_body = export_rows_to_csv(["Front", "Back", "Tags"], anki_data)
    else:
        cols = _parse_export_columns_api(columns)
        projected = [project_export_columns(r, cols) for r in full_rows]
        csv_body = export_rows_to_csv(cols, projected)

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
