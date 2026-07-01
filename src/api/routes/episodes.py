"""Episode endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.models import Episode, EpisodeVocabulary, UserVocabulary
from src.rag import answer_question, search_episodes

from ..deps import get_db, get_dictionary
from ..session import get_user_id

router = APIRouter(tags=["episodes"])


class EpisodeListItem(BaseModel):
    id: int
    video_id: str
    title: str
    published_at: Optional[str] = None
    thumbnail_url: Optional[str] = None
    topics: Optional[str] = None
    vocab_count: int = 0

    model_config = {"from_attributes": True}


class SegmentOut(BaseModel):
    id: int
    text: str
    translation_en: Optional[str] = None
    start_time: float
    duration: float

    model_config = {"from_attributes": True}


class VocabWordOut(BaseModel):
    vocabulary_id: int
    lemma: str
    pos: Optional[str] = None
    occurrence_count: int = 0
    surface_forms: Optional[str] = None
    example_sentence: Optional[str] = None
    meaning: Optional[str] = None
    meaning_en: Optional[str] = None
    status: str = "new"

    model_config = {"from_attributes": True}


class ArticleOut(BaseModel):
    topic: str
    title: str
    url: str
    snippet: str = ""


class EpisodeSearchResult(BaseModel):
    id: int
    video_id: str
    title: str
    published_at: Optional[str] = None
    thumbnail_url: Optional[str] = None

    model_config = {"from_attributes": True}


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    episodes: list[EpisodeSearchResult]


class EpisodeDetailOut(BaseModel):
    id: int
    video_id: str
    title: str
    description: Optional[str] = None
    published_at: Optional[str] = None
    topics: Optional[str] = None
    segments: list[SegmentOut]
    vocabulary: list[VocabWordOut]
    related_articles: list[ArticleOut]

    model_config = {"from_attributes": True}


@router.get("/episodes", response_model=list[EpisodeListItem])
def list_episodes(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List episodes (newest first) with vocabulary counts."""
    vocab_counts = (
        db.query(
            EpisodeVocabulary.episode_id,
            func.count(EpisodeVocabulary.id).label("vocab_count"),
        )
        .group_by(EpisodeVocabulary.episode_id)
        .subquery()
    )

    rows = (
        db.query(Episode, func.coalesce(vocab_counts.c.vocab_count, 0))
        .outerjoin(vocab_counts, Episode.id == vocab_counts.c.episode_id)
        .filter(Episode.transcript_fetched == True)  # noqa: E712
        .order_by(Episode.published_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        EpisodeListItem(
            id=ep.id,
            video_id=ep.video_id,
            title=ep.title,
            published_at=ep.published_at.isoformat() if ep.published_at else None,
            thumbnail_url=ep.thumbnail_url,
            topics=ep.topics,
            vocab_count=count,
        )
        for ep, count in rows
    ]


def _to_search_result(ep: Episode) -> EpisodeSearchResult:
    return EpisodeSearchResult(
        id=ep.id,
        video_id=ep.video_id,
        title=ep.title,
        published_at=ep.published_at.isoformat() if ep.published_at else None,
        thumbnail_url=ep.thumbnail_url,
    )


# Registered before /episodes/{episode_id} so "search" isn't matched as an episode_id.
@router.get("/episodes/search", response_model=list[EpisodeSearchResult])
def search_episodes_route(q: str, limit: int = 5, db: Session = Depends(get_db)):
    """Semantic search over episodes (requires Postgres + pgvector + OPENAI_API_KEY)."""
    try:
        episodes = search_episodes(db, q, limit=limit)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return [_to_search_result(ep) for ep in episodes]


@router.post("/episodes/ask", response_model=AskResponse)
def ask_episodes_route(body: AskRequest, db: Session = Depends(get_db)):
    """RAG: answer a question using the most relevant episodes as context."""
    try:
        result = answer_question(db, body.question)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return AskResponse(
        answer=result["answer"],
        episodes=[_to_search_result(ep) for ep in result["episodes"]],
    )


@router.get("/episodes/{episode_id}", response_model=EpisodeDetailOut)
def get_episode(
    episode_id: int,
    db: Session = Depends(get_db),
    dictionary=Depends(get_dictionary),
    user_id: int = Depends(get_user_id),
):
    """
    Get full episode detail: segments, vocabulary with dictionary data, articles.

    Vocabulary status is per-user, resolved from X-Session-Token header.
    Without token, uses legacy shared user (user_id=1).
    """
    episode = (
        db.query(Episode)
        .options(
            joinedload(Episode.subtitle_segments),
            joinedload(Episode.episode_vocabulary).joinedload(EpisodeVocabulary.vocabulary_item),
        )
        .filter(Episode.id == episode_id)
        .first()
    )
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    # Segments
    segments = sorted(episode.subtitle_segments, key=lambda s: s.start_time)
    segments_out = [
        SegmentOut(
            id=s.id,
            text=s.text,
            translation_en=s.translation_en,
            start_time=s.start_time,
            duration=s.duration,
        )
        for s in segments
    ]

    # Vocabulary with dictionary enrichment + user status (per-user via token)
    user_statuses = {
        uv.vocabulary_id: uv.status
        for uv in db.query(UserVocabulary).filter_by(user_id=user_id).all()
    }

    vocab_out = []
    for ev in episode.episode_vocabulary or []:
        v = ev.vocabulary_item
        if v.lemma.lower() in ("journaal",):
            continue
        entry = dictionary.lookup_with_example(v.lemma, v.pos)
        gloss_nl = v.translation or (entry.get("gloss") if entry else None)
        gloss_en = entry.get("gloss_en") if entry else None

        vocab_out.append(
            VocabWordOut(
                vocabulary_id=v.id,
                lemma=v.lemma,
                pos=v.pos,
                occurrence_count=ev.occurrence_count or 0,
                surface_forms=ev.surface_forms,
                example_sentence=ev.example_sentence,
                meaning=gloss_nl or gloss_en or None,
                meaning_en=gloss_en,
                status=user_statuses.get(v.id, "new"),
            )
        )
    vocab_out.sort(key=lambda w: w.occurrence_count, reverse=True)

    # Related articles
    articles_out = []
    if episode.related_articles:
        try:
            raw = json.loads(episode.related_articles)
            articles_out = [ArticleOut(**a) for a in raw]
        except (json.JSONDecodeError, TypeError):
            pass

    return EpisodeDetailOut(
        id=episode.id,
        video_id=episode.video_id,
        title=episode.title,
        description=episode.description,
        published_at=episode.published_at.isoformat() if episode.published_at else None,
        topics=episode.topics,
        segments=segments_out,
        vocabulary=vocab_out,
        related_articles=articles_out,
    )
