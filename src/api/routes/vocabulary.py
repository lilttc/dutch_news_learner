"""User vocabulary status endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.models import UserVocabulary, VocabularyItem

from ..deps import get_db
from ..session import get_user_id

router = APIRouter(tags=["vocabulary"])

VALID_STATUSES = {"new", "learning", "known"}

# Learner-written note per word (export / Anki); empty / null stored as NULL
USER_SENTENCE_MAX_LEN = 2000


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
