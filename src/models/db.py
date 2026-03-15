"""
Database models for Dutch News Learner.

Adapted from tai8bot. Episode = one news video, SubtitleSegment = one subtitle line.
Vocabulary tables (VocabularyItem, EpisodeVocabulary, UserVocabulary) added in Phase 2.
"""

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class Episode(Base):
    """One news episode (YouTube video)."""

    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True)
    video_id = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    published_at = Column(DateTime)
    position = Column(Integer)  # Position in playlist
    thumbnail_url = Column(String(500))

    # Source identifier (e.g., "drie_onderwerpen")
    source = Column(String(100), index=True, default="drie_onderwerpen")

    # Transcript status
    transcript_fetched = Column(Boolean, default=False)
    transcript_language = Column(String(10))
    transcript_is_generated = Column(Boolean)

    # Episode summary (Phase 3 - optional AI enrichment)
    summary = Column(Text)

    # Topics for related reading (pipe-separated, e.g. "olie|fatbikes|Flevoland")
    topics = Column(Text)

    # Related articles JSON: [{"topic": "...", "title": "...", "url": "...", "snippet": "..."}, ...]
    related_articles = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subtitle_segments = relationship(
        "SubtitleSegment",
        back_populates="episode",
        cascade="all, delete-orphan",
    )
    episode_vocabulary = relationship(
        "EpisodeVocabulary",
        back_populates="episode",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Episode(video_id='{self.video_id}', title='{self.title[:40]}...')>"


class SubtitleSegment(Base):
    """One subtitle/transcript segment with timestamps."""

    __tablename__ = "subtitle_segments"

    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False, index=True)
    video_id = Column(String(20), nullable=False, index=True)  # Denormalized for queries

    text = Column(Text, nullable=False)
    translation_en = Column(Text)  # English translation (LLM-generated)
    start_time = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    end_time = Column(Float)  # start_time + duration

    created_at = Column(DateTime, default=datetime.utcnow)

    episode = relationship("Episode", back_populates="subtitle_segments")

    def __repr__(self):
        return f"<SubtitleSegment(video_id='{self.video_id}', start={self.start_time}, text='{self.text[:30]}...')>"


class VocabularyItem(Base):
    """
    Master vocabulary list — one row per unique lemma across all episodes.

    Stores the canonical form (lemma) and optional enrichment (translation, difficulty).
    Translation can be added later via dictionary integration or API.
    """

    __tablename__ = "vocabulary_items"

    id = Column(Integer, primary_key=True)
    lemma = Column(String(100), unique=True, nullable=False, index=True)
    pos = Column(String(20), index=True)  # NOUN, VERB, ADJ, ADV from spaCy

    # Enrichment (optional — can be populated later via dictionary/API)
    translation = Column(String(200))  # English translation
    frequency_rank = Column(Integer)  # From Subtlex-NL or similar (lower = more common)
    cefr_level = Column(String(10))  # A1, A2, B1, B2, C1, C2

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    episode_vocabulary = relationship(
        "EpisodeVocabulary",
        back_populates="vocabulary_item",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<VocabularyItem(lemma='{self.lemma}', pos='{self.pos}')>"


class UserVocabulary(Base):
    """
    Per-user vocabulary status: known, learning, or new.

    Lets learners mark words and filter out known vocabulary to focus on
    what they're still learning. Currently single-user (user_id always 1);
    will support multi-user after auth migration.
    """

    __tablename__ = "user_vocabulary"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, default=1, index=True)
    vocabulary_id = Column(
        Integer, ForeignKey("vocabulary_items.id"), nullable=False, index=True
    )
    status = Column(
        String(20), nullable=False, default="new", index=True
    )  # "new", "learning", "known"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vocabulary_item = relationship("VocabularyItem", backref="user_vocabulary")

    def __repr__(self):
        return f"<UserVocabulary(user={self.user_id}, vocab={self.vocabulary_id}, status='{self.status}')>"


class EpisodeVocabulary(Base):
    """
    Junction table: which vocabulary items appear in which episode.

    Links Episode ↔ VocabularyItem with per-episode counts and an example sentence.
    Enables: "word X appears N times in this episode" and "recurring across episodes".
    """

    __tablename__ = "episode_vocabulary"

    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False, index=True)
    vocabulary_id = Column(
        Integer, ForeignKey("vocabulary_items.id"), nullable=False, index=True
    )

    occurrence_count = Column(Integer, nullable=False, default=1)
    example_sentence = Column(Text)  # Best example from this episode
    example_timestamp = Column(Float)  # Start time of example subtitle segment
    surface_forms = Column(Text)  # Pipe-separated word forms seen (e.g. "gaan|gaat|ging")

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    episode = relationship("Episode", back_populates="episode_vocabulary")
    vocabulary_item = relationship(
        "VocabularyItem", back_populates="episode_vocabulary"
    )

    def __repr__(self):
        return f"<EpisodeVocabulary(episode_id={self.episode_id}, vocab_id={self.vocabulary_id}, count={self.occurrence_count})>"


# Database helpers

def get_engine(db_url: str = "sqlite:///data/dutch_news.db"):
    """Create database engine."""
    return create_engine(db_url, echo=False)


def get_session(engine=None):
    """Create database session."""
    if engine is None:
        engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(db_url: str = "sqlite:///data/dutch_news.db"):
    """Initialize database (create all tables)."""
    import os

    # Ensure data directory exists
    db_dir = os.path.dirname(db_url.replace("sqlite:///", ""))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    engine = get_engine(db_url)
    Base.metadata.create_all(engine)
    _migrate_schema(engine)
    print(f"✅ Database initialized: {db_url}")
    return engine


def _migrate_schema(engine):
    """Add new columns to existing tables (idempotent)."""
    from sqlalchemy import text

    migrations = [
        "ALTER TABLE episode_vocabulary ADD COLUMN surface_forms TEXT",
        "ALTER TABLE subtitle_segments ADD COLUMN translation_en TEXT",
        "ALTER TABLE episodes ADD COLUMN topics TEXT",
        "ALTER TABLE episodes ADD COLUMN related_articles TEXT",
        # UserVocabulary table for known/learning word tracking
        """CREATE TABLE IF NOT EXISTS user_vocabulary (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL DEFAULT 1,
            vocabulary_id INTEGER NOT NULL REFERENCES vocabulary_items(id),
            status VARCHAR(20) NOT NULL DEFAULT 'new',
            created_at DATETIME,
            updated_at DATETIME
        )""",
        "CREATE INDEX IF NOT EXISTS ix_user_vocabulary_user_id ON user_vocabulary(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_vocabulary_vocabulary_id ON user_vocabulary(vocabulary_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_vocabulary_status ON user_vocabulary(status)",
    ]
    for sql in migrations:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            pass  # Column likely already exists
