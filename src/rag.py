"""
Shared semantic search + RAG logic for episodes.

Used by three surfaces that all need the same retrieve-then-answer behavior:
src/api/routes/episodes.py (FastAPI), app/main.py ("Ask the news" page), and
scripts/run_eval.py (retrieval evaluation). Centralized here instead of
duplicating the OpenAI-calling logic in each.

Requires: OPENAI_API_KEY in .env. Semantic search additionally requires a
Postgres database with the pgvector extension and populated Episode.embedding
columns (see scripts/embed_episodes.py) - it is unavailable on the SQLite dev
fallback, which stores embedding as plain TEXT.
"""

# Load-bearing: `OpenAI` is a TYPE_CHECKING-only import below, so the annotations
# in this module must stay lazy (strings). Don't remove this line.
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from src.models import Episode, SubtitleSegment

if TYPE_CHECKING:
    from openai import OpenAI

EMBEDDING_MODEL = "text-embedding-3-small"
ANSWER_MODEL = "gpt-4o"


def get_client() -> OpenAI:
    """
    Build an OpenAI client from ``OPENAI_API_KEY``.

    ``openai`` (and its Pydantic dependency) is imported lazily here so that
    merely importing this module - which the Streamlit app does on every page
    load for ``is_semantic_search_available`` - stays cheap and framework-light.
    """
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Add it to .env")
    return OpenAI(api_key=api_key)


def embed_text(client: OpenAI, text: str) -> list[float]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def is_semantic_search_available(session) -> bool:
    """
    Semantic search needs Postgres + pgvector. The SQLite dev fallback stores
    Episode.embedding as plain TEXT and can't run similarity queries.
    """
    return session.get_bind().dialect.name == "postgresql"


def search_episodes(
    session,
    query: str,
    limit: int = 5,
    client: OpenAI | None = None,
) -> list[Episode]:
    """Embed `query` and return the `limit` most similar episodes by cosine distance."""
    if not is_semantic_search_available(session):
        raise RuntimeError("Semantic search requires a Postgres database with pgvector")
    client = client or get_client()
    query_vec = embed_text(client, query)
    return (
        session.query(Episode)
        .filter(Episode.embedding.is_not(None))
        .order_by(Episode.embedding.cosine_distance(query_vec))
        .limit(limit)
        .all()
    )


def episode_transcript(session, episode: Episode, max_chars: int = 1500) -> str:
    """First `max_chars` of the episode transcript, segments joined in order."""
    segments = (
        session.query(SubtitleSegment)
        .filter(SubtitleSegment.episode_id == episode.id)
        .order_by(SubtitleSegment.start_time)
        .all()
    )
    transcript = " ".join(s.text for s in segments)
    return transcript[:max_chars]


def answer_question(
    session,
    question: str,
    client: OpenAI | None = None,
) -> dict:
    """
    Retrieve the top-3 most relevant episodes and ask GPT-4o to answer `question`
    using their transcripts as context, citing episode dates/titles.

    Returns {"answer": str, "episodes": [Episode, ...]}.
    """
    client = client or get_client()
    episodes = search_episodes(session, question, limit=3, client=client)
    if not episodes:
        return {"answer": "No matching episodes found.", "episodes": []}

    context_blocks = []
    for ep in episodes:
        date = ep.published_at.strftime("%Y-%m-%d") if ep.published_at else "unknown date"
        context_blocks.append(f"[{date}] {ep.title}\n{episode_transcript(session, ep)}")
    context = "\n\n---\n\n".join(context_blocks)

    prompt = f"""You answer questions about Dutch news using only the episode excerpts below.
Cite the episode date(s) you used in your answer. If the excerpts don't contain the
answer, say so plainly instead of guessing.

Episodes:
{context}

Question: {question}

Answer:"""

    response = client.chat.completions.create(
        model=ANSWER_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You answer questions about Dutch news episodes, citing your sources.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    answer = response.choices[0].message.content.strip()
    return {"answer": answer, "episodes": episodes}
