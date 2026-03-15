"""User vocabulary status endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models import UserVocabulary, VocabularyItem

from ..deps import get_db

router = APIRouter(tags=["vocabulary"])

VALID_STATUSES = {"new", "learning", "known"}


class VocabStatusUpdate(BaseModel):
    status: str


class VocabStatusOut(BaseModel):
    vocabulary_id: int
    lemma: str
    status: str

    model_config = {"from_attributes": True}


@router.get("/vocabulary/status", response_model=list[VocabStatusOut])
def list_vocab_statuses(
    status: str | None = None,
    db: Session = Depends(get_db),
    user_id: int = 1,
):
    """List all vocabulary items with their user status."""
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
        )
        for uv, vi in query.all()
    ]


@router.put("/vocabulary/{vocabulary_id}/status", response_model=VocabStatusOut)
def update_vocab_status(
    vocabulary_id: int,
    body: VocabStatusUpdate,
    db: Session = Depends(get_db),
    user_id: int = 1,
):
    """Set a word's learning status (new, learning, known)."""
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
    )
