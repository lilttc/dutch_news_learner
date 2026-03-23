"""
Database models for Dutch News Learner.

Adapted from tai8bot. Episode = one news video, SubtitleSegment = one subtitle line.
Vocabulary tables (VocabularyItem, EpisodeVocabulary, UserVocabulary) added in Phase 2.
"""

import os
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
    UniqueConstraint,
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
    translation = Column(Text)  # English translation
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


class User(Base):
    """
    Registered user (Phase 6F — email auth).

    id >= 1_000_000 to avoid collision with AnonymousSession (id 2+) and
    legacy (user_id=1). UserVocabulary.user_id can be: 1=legacy,
    2..999999=anonymous session, 1000000+=registered user.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"


class AnonymousSession(Base):
    """
    Anonymous session for per-user vocabulary (Phase 6E).

    Each visitor gets a unique token (UUID) stored in localStorage (Next.js) or
    URL param (Streamlit). The session's id is used as user_id in UserVocabulary,
    giving each visitor their own known/learning status without login.

    Legacy: user_id=1 is reserved for shared/anonymous usage when no token.
    New sessions receive id=2, 3, 4... (id=1 is a sentinel row).
    """

    __tablename__ = "anonymous_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(36), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AnonymousSession(id={self.id}, token='{self.token[:8]}...')>"


class UserVocabulary(Base):
    """
    Per-user vocabulary status: known, learning, or new.

    Lets learners mark words and filter out known vocabulary to focus on
    what they're still learning. user_id=1 is legacy (shared); user_id>=2
    are anonymous sessions (Phase 6E). user_sentence: optional learner note
    for export (Anki, CSV).
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
    # Learner-written example sentence (export / Anki); optional
    user_sentence = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vocabulary_item = relationship("VocabularyItem", backref="user_vocabulary")

    def __repr__(self):
        return f"<UserVocabulary(user={self.user_id}, vocab={self.vocabulary_id}, status='{self.status}')>"


class UserEpisodeWatch(Base):
    """
    User explicitly marked an episode as watched (Streamlit / future API).

    user_id uses the same space as UserVocabulary (1=legacy, anonymous session ids,
    registered user ids). One row per (user_id, episode_id).
    """

    __tablename__ = "user_episode_watches"
    __table_args__ = (
        UniqueConstraint("user_id", "episode_id", name="uq_user_episode_watch"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False, index=True)
    watched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    episode = relationship("Episode", backref="user_watches")

    def __repr__(self):
        return f"<UserEpisodeWatch(user={self.user_id}, episode={self.episode_id})>"


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


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

_SQLITE_FALLBACK = "sqlite:///data/dutch_news.db"


def _resolve_url(db_url: str | None = None) -> str:
    """Return the database URL to use.

    Priority: explicit arg > DATABASE_URL env var > SQLite fallback.
    """
    if db_url:
        return db_url
    return os.environ.get("DATABASE_URL", _SQLITE_FALLBACK)


def _is_postgres(url: str) -> bool:
    return url.startswith("postgresql") or url.startswith("postgres://")


def get_engine(db_url: str | None = None):
    """Create a SQLAlchemy engine.

    * Postgres (via DATABASE_URL): uses a connection pool (5 connections,
      overflow to 10) and requires SSL for Neon.
    * SQLite (local dev): simple single-connection engine.
    """
    url = _resolve_url(db_url)

    if _is_postgres(url):
        from sqlalchemy import event

        eng = create_engine(
            url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Reconnect if Neon scaled to zero and closed idle connections
            connect_args={"sslmode": "require"},
        )

        @event.listens_for(eng, "connect")
        def _reset_lock_timeout(dbapi_conn, connection_record):
            with dbapi_conn.cursor() as cur:
                cur.execute("SET lock_timeout = '0'")

        return eng

    return create_engine(url, echo=False)


def get_session(engine=None):
    """Create database session."""
    if engine is None:
        engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(db_url: str | None = None):
    """Initialize database — create tables and run migrations."""
    url = _resolve_url(db_url)

    if not _is_postgres(url):
        db_dir = os.path.dirname(url.replace("sqlite:///", ""))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    engine = get_engine(url)
    Base.metadata.create_all(engine)
    _migrate_schema(engine)
    label = "Postgres" if _is_postgres(url) else url
    print(f"✅ Database initialized: {label}")
    return engine


def _pg_add_column(table: str, column: str, col_type: str) -> str:
    """Generate a Postgres DO-block that adds a column only if it doesn't exist."""
    return f"""DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='{table}' AND column_name='{column}'
        ) THEN
            ALTER TABLE {table} ADD COLUMN {column} {col_type};
        END IF;
    END $$"""


def _migrate_schema(engine):
    """Add new columns / tables to existing schema (idempotent).

    Handles syntax differences between SQLite and Postgres:
    - SQLite uses INTEGER PRIMARY KEY (auto-increment implied).
    - Postgres uses SERIAL PRIMARY KEY.
    """
    from sqlalchemy import text

    pg = _is_postgres(str(engine.url))
    pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY"

    if pg:
        migrations = [
            _pg_add_column("episode_vocabulary", "surface_forms", "TEXT"),
            _pg_add_column("subtitle_segments", "translation_en", "TEXT"),
            _pg_add_column("episodes", "topics", "TEXT"),
            _pg_add_column("episodes", "related_articles", "TEXT"),
            """DO $$ BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='vocabulary_items' AND column_name='translation'
                    AND data_type='character varying'
                ) THEN
                    ALTER TABLE vocabulary_items ALTER COLUMN translation TYPE TEXT;
                END IF;
            END $$""",
            f"""CREATE TABLE IF NOT EXISTS user_vocabulary (
                id {pk},
                user_id INTEGER NOT NULL DEFAULT 1,
                vocabulary_id INTEGER NOT NULL REFERENCES vocabulary_items(id),
                status VARCHAR(20) NOT NULL DEFAULT 'new',
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS ix_user_vocabulary_user_id ON user_vocabulary(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_vocabulary_vocabulary_id ON user_vocabulary(vocabulary_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_vocabulary_status ON user_vocabulary(status)",
            # Phase 6E: anonymous sessions for per-user vocab
            f"""CREATE TABLE IF NOT EXISTS anonymous_sessions (
                id {pk},
                token VARCHAR(36) NOT NULL UNIQUE,
                created_at TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS ix_anonymous_sessions_token ON anonymous_sessions(token)",
            # Reserve id=1 for legacy (user_id=1); real sessions get id=2+
            """INSERT INTO anonymous_sessions (id, token, created_at)
               VALUES (1, '__legacy__', NOW())
               ON CONFLICT (id) DO NOTHING""",
            # Ensure sequence yields id>=2 for new inserts
            """SELECT setval(
                pg_get_serial_sequence('anonymous_sessions', 'id'),
                GREATEST(1, (SELECT COALESCE(MAX(id), 1) FROM anonymous_sessions))
            )""",
            # Phase 6F: users table for email auth (id >= 1000000 to avoid collision)
            f"""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)",
            # Postgres: create sequence starting at 1000000 for users
            """CREATE SEQUENCE IF NOT EXISTS users_id_seq START 1000000""",
            """ALTER TABLE users ALTER COLUMN id SET DEFAULT nextval('users_id_seq')""",
            # Vocab export: optional learner sentence per user per word
            _pg_add_column("user_vocabulary", "user_sentence", "TEXT"),
            # Explicit "mark episode watched" per user (same user_id space as user_vocabulary)
            f"""CREATE TABLE IF NOT EXISTS user_episode_watches (
                id {pk},
                user_id INTEGER NOT NULL,
                episode_id INTEGER NOT NULL REFERENCES episodes(id),
                watched_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_user_episode_watch UNIQUE (user_id, episode_id)
            )""",
            "CREATE INDEX IF NOT EXISTS ix_user_episode_watches_user_id ON user_episode_watches(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_episode_watches_episode_id ON user_episode_watches(episode_id)",
        ]
    else:
        migrations = [
            "ALTER TABLE episode_vocabulary ADD COLUMN surface_forms TEXT",
            "ALTER TABLE subtitle_segments ADD COLUMN translation_en TEXT",
            "ALTER TABLE episodes ADD COLUMN topics TEXT",
            "ALTER TABLE episodes ADD COLUMN related_articles TEXT",
            f"""CREATE TABLE IF NOT EXISTS user_vocabulary (
                id {pk},
                user_id INTEGER NOT NULL DEFAULT 1,
                vocabulary_id INTEGER NOT NULL REFERENCES vocabulary_items(id),
                status VARCHAR(20) NOT NULL DEFAULT 'new',
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS ix_user_vocabulary_user_id ON user_vocabulary(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_vocabulary_vocabulary_id ON user_vocabulary(vocabulary_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_vocabulary_status ON user_vocabulary(status)",
            # Phase 6E: anonymous sessions for per-user vocab
            f"""CREATE TABLE IF NOT EXISTS anonymous_sessions (
                id {pk},
                token VARCHAR(36) NOT NULL UNIQUE,
                created_at TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS ix_anonymous_sessions_token ON anonymous_sessions(token)",
            # Reserve id=1 for legacy; real sessions get id=2+ (SQLite: OR IGNORE)
            "INSERT OR IGNORE INTO anonymous_sessions (id, token, created_at) VALUES (1, '__legacy__', datetime('now'))",
            # Phase 6F: users table (SQLite: no sequence; first insert uses 1000000)
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)",
            # SQLite: insert placeholder so next id is 1000000 (AUTOINCREMENT uses max+1)
            "INSERT OR IGNORE INTO users (id, email, password_hash, created_at) VALUES (999999, '__internal_seed_6f__', '', datetime('now'))",
            "ALTER TABLE user_vocabulary ADD COLUMN user_sentence TEXT",
            f"""CREATE TABLE IF NOT EXISTS user_episode_watches (
                id {pk},
                user_id INTEGER NOT NULL,
                episode_id INTEGER NOT NULL REFERENCES episodes(id),
                watched_at TIMESTAMP NOT NULL,
                UNIQUE (user_id, episode_id)
            )""",
            "CREATE INDEX IF NOT EXISTS ix_user_episode_watches_user_id ON user_episode_watches(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_episode_watches_episode_id ON user_episode_watches(episode_id)",
        ]

    for sql in migrations:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            pass  # Column/table likely already exists
