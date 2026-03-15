# Dutch News Learner — Architecture

This document describes the system architecture, data flow, and design decisions for Dutch News Learner.

---

## 1. High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DUTCH NEWS LEARNER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐   │
│   │   INGESTION  │────▶│  PROCESSING  │────▶│       STORAGE             │   │
│   │              │     │              │     │                          │   │
│   │ YouTube API  │     │ Tokenization │     │  SQLite / PostgreSQL     │   │
│   │ Transcripts  │     │ Lemmatization│     │  Episodes, Vocabulary,   │   │
│   │              │     │ Frequency    │     │  User Progress, Quizzes   │   │
│   └──────────────┘     └──────────────┘     └────────────┬─────────────┘   │
│                                                          │                  │
│                                                          ▼                  │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                     SERVING LAYER                                      │  │
│   │                                                                       │  │
│   │   FastAPI (REST)  ◀──────▶  Streamlit (Web UI)                         │  │
│   │                                                                       │  │
│   │   Endpoints: episodes, vocabulary, quiz, user-progress                 │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Pipeline

### 2.1 Source Ingestion

```
YouTube Data API v3
        │
        ├── Playlist metadata (NOS Journaal in Makkelijke Taal)
        ├── Video IDs, titles, publish dates
        └── Thumbnails, descriptions
        │
        ▼
youtube-transcript-api
        │
        ├── Subtitle segments (text, start, duration)
        ├── Language: nl (Dutch)
        └── Auto-generated or manual captions
        │
        ▼
Raw transcript stored per episode
```

**Key decisions:**

- Use `youtube-transcript-api` for subtitles (no API key required, reliable)
- Use YouTube Data API v3 for playlist metadata (requires API key)
- Prefer `nl` language for transcripts; fallback to first available

### 2.2 Text Processing Pipeline

```
Raw transcript (list of segments)
        │
        ▼
┌───────────────────┐
│ 1. Normalization  │  Lowercase, strip punctuation, fix encoding
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 2. Tokenization   │  spaCy nl_core_news_md
│    + Lemmatization│  → lemma per token
│    + POS tagging  │  → NOUN, VERB, ADJ, ADV, etc.
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 3. Filtering      │  Keep: NOUN, VERB, ADJ, ADV
│                   │  Drop: STOP, PUNCT, PROPN (names), NUM
│                   │  Min length: 2 chars
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 4. Aggregation    │  Count per lemma per episode
│                   │  Store example sentences
│                   │  Link to subtitle timestamps
└─────────┬─────────┘
          │
          ▼
Candidate vocabulary list
```

### 2.3 Vocabulary Enrichment

```
Candidate vocabulary (lemma + count + example)
        │
        ├─────────────────────────────────────┐
        │                                     │
        ▼                                     ▼
┌───────────────────┐               ┌───────────────────┐
│ Frequency lookup  │               │ Translation       │
│ (Subtlex-NL)      │               │ (WordNet / API)   │
│ → CEFR estimate   │               │ → English meaning │
│ → Difficulty rank │               │                   │
└─────────┬─────────┘               └─────────┬─────────┘
          │                                     │
          └─────────────────┬───────────────────┘
                            │
                            ▼
              Enriched VocabularyItem
```

### 2.4 Cross-Episode Frequency

```
Episode 1 vocab ──┐
Episode 2 vocab ──┼──▶ Aggregate by lemma
Episode 3 vocab ──┤    → episode_count, total_count
    ...          ──┘    → last_seen_date
                            │
                            ▼
              Recurring vocabulary ranking
```

### 2.5 Optional LLM Enrichment

```
Episode (title, description, transcript)
        │
        ├─────────────────────────────────────┐
        │                                     │
        ▼                                     ▼
┌───────────────────┐               ┌───────────────────┐
│ translate_segments │               │ extract_topics    │
│ (OpenAI)          │               │ (OpenAI)          │
│ → SubtitleSegment │               │ → Episode.topics   │
│   .translation_en │               │   (pipe-separated)│
└───────────────────┘               └─────────┬─────────┘
                                              │
                                              ▼
                                    Related reading: Google search
                                    site:nos.nl, date ±2 days
```

---

## 3. Data Model

### 3.1 Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────────┐       ┌──────────────────┐
│    Episode      │       │  SubtitleSegment    │       │  VocabularyItem  │
├─────────────────┤       ├─────────────────────┤       ├──────────────────┤
│ id (PK)         │───┐   │ id (PK)             │       │ id (PK)          │
│ video_id        │   │   │ episode_id (FK)      │       │ lemma (unique)    │
│ title           │   └──│ start_time           │       │ pos               │
│ published_at    │      │ end_time             │       │ translation       │
│ summary         │      │ text                 │       │ frequency_rank    │
│ thumbnail_url   │      │ normalized_text      │       │ cefr_level        │
└────────┬────────┘      └─────────────────────┘       └────────┬─────────┘
         │                                                       │
         │              ┌─────────────────────┐                  │
         │              │ EpisodeVocabulary   │                  │
         └──────────────│ episode_id (FK)     │◀─────────────────┘
                        │ vocabulary_id (FK)  │
                        │ occurrence_count    │
                        │ example_sentence    │
                        │ example_timestamp   │
                        └─────────────────────┘
                                    
┌──────────────────┐       ┌─────────────────────┐
│  UserVocabulary  │       │  QuizSession        │
├──────────────────┤       ├─────────────────────┤
│ id (PK)          │       │ id (PK)             │
│ vocabulary_id(FK)│       │ user_id             │
│ status           │       │ quiz_date           │
│ first_seen_at    │       │ score                │
│ last_reviewed_at │       │ duration_seconds    │
│ times_seen       │       └──────────┬──────────┘
│ times_correct    │                  │
│ times_incorrect  │       ┌──────────▼──────────┐
└──────────────────┘       │  QuizItem           │
                           ├─────────────────────┤
                           │ session_id (FK)     │
                           │ vocabulary_id (FK)  │
                           │ question_type       │
                           │ user_answer         │
                           │ is_correct          │
                           └─────────────────────┘
```

### 3.2 Table Definitions

| Table | Purpose |
|-------|---------|
| **Episode** | One NOS Journaal video. Stores YouTube metadata, summary, publish date, topics (pipe-separated for Related reading). |
| **SubtitleSegment** | One subtitle line. Text, start/end timestamps, optional translation_en (LLM), links to episode. |
| **VocabularyItem** | Master vocabulary. Lemma, POS, translation, frequency rank, CEFR. |
| **EpisodeVocabulary** | Junction: which words appear in which episode, with counts and examples. |
| **UserVocabulary** | User's relationship to each word: status, review dates, quiz performance. |
| **QuizSession** | One quiz attempt. Date, score, duration. |
| **QuizItem** | One question in a quiz. Vocabulary, answer, correctness. |

### 3.3 User Vocabulary Status

| Status | Meaning |
|--------|---------|
| `new` | Just seen, not yet saved |
| `learning` | Saved, in review queue |
| `known` | User marked as known |
| `ignored` | User chose to ignore |

---

## 4. Learning Pipeline

### 4.1 Daily Learning Flow

```
User opens app
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Show latest episode                                           │
│    - Embedded video                                               │
│    - Subtitle transcript (clickable words → definition bubble)   │
│    - Optional English translation per line (toggle, default off) │
│    - Extracted vocabulary list                                    │
│    - Related reading (NOS links, date-filtered ±2 days)           │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. User clicks word → modal with translation, example, status    │
│    - "Save to vocabulary" → UserVocabulary.status = 'learning'   │
│    - "I know this" → UserVocabulary.status = 'known'             │
│    - "Ignore" → UserVocabulary.status = 'ignored'                 │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Daily quiz                                                    │
│    - Pool: new words from today + learning + previously wrong     │
│    - 5–10 questions (template-based: translation multiple choice) │
│    - Record results in QuizSession + QuizItem                    │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Update UserVocabulary                                         │
│    - last_reviewed_at, times_correct, times_incorrect             │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Quiz Question Generation

**Phase 1 (MVP):** Template-based, no LLM

```
For each vocabulary item in quiz pool:
  1. Get correct translation
  2. Select 3 distractors from:
     - Same POS, similar frequency
     - Random from same episode
  3. Shuffle options (A, B, C, D)
  4. Store question + correct index
```

**Phase 2 (Future):** Add cloze deletion, context-based questions, optional LLM generation.

### 4.3 Vocabulary Ranking (Personalization)

When displaying vocabulary, rank by:

1. **User status** — `learning` > `new` > `known` (hide `ignored`)
2. **Recurrence** — Higher episode count = higher priority
3. **Episode frequency** — More appearances in this episode = more important
4. **Difficulty** — Filter by CEFR (e.g., show A2–B2 only)
5. **Quiz performance** — Previously incorrect = higher priority

---

## 5. Component Architecture

### 5.1 Ingestion Module

```
src/ingestion/
├── __init__.py
├── youtube.py          # YouTubePlaylistFetcher, YouTubeTranscriptFetcher
├── storage.py          # Save episodes + segments to DB (or in ingest_playlist)
└── config.py           # Playlist IDs, language preferences
```

**Reusable from tai8bot:** `YouTubePlaylistFetcher`, `YouTubeTranscriptFetcher` (with `preferred_languages=['nl']`)

### 5.2 Processing Module

```
src/processing/
├── __init__.py
├── tokenizer.py        # spaCy pipeline wrapper
├── vocabulary.py       # Extract, filter, aggregate vocabulary
├── enrichment.py       # Frequency lookup, translation
└── frequency.py        # Cross-episode frequency calculation
```

### 5.3 API Layer

```
src/api/
├── __init__.py
├── main.py             # FastAPI app
├── routes/
│   ├── episodes.py     # GET /episodes, GET /episodes/{id}
│   ├── vocabulary.py   # GET /vocabulary, POST /vocabulary/{id}/status
│   ├── quiz.py         # GET /quiz/today, POST /quiz/submit
│   └── user.py         # GET /user/progress
└── schemas.py          # Pydantic models
```

### 5.4 Frontend (Streamlit)

```
app/
├── main.py             # Entry point — episode viewer, transcript, vocabulary, Related reading
└── (single-page MVP)   # Clickable transcript with definition bubbles, translation toggle
```

---

## 6. External Dependencies

| Dependency | Purpose | Notes |
|------------|---------|-------|
| **YouTube Data API v3** | Playlist metadata | Requires API key |
| **youtube-transcript-api** | Subtitle extraction | No key, may need updates |
| **spaCy nl_core_news_md** | Dutch NLP | ~50MB model |
| **Subtlex-NL** | Word frequency | Offline CSV/JSON |
| **Open Dutch WordNet** | Translations | Optional, offline |
| **OpenAI API** | Segment translation, topic extraction | Optional, for translation_en and Episode.topics |

---

## 7. Deployment Considerations

### 7.1 Personal Version

- **Single user** — No auth required
- **SQLite** — File-based, no server
- **Local run** — `streamlit run app/main.py`
- **Cron** — Daily ingestion script (e.g., 6am)

### 7.2 Public Platform (Future)

- **PostgreSQL** — Multi-user, concurrent access
- **Authentication** — Auth0, Supabase, or similar
- **Background jobs** — Celery, Dramatiq, or cloud scheduler
- **Hosting** — Render, Railway, or VPS
- **Docker** — Containerized deployment

---

## 8. Design Decisions Summary

| Decision | Rationale |
|----------|-----------|
| spaCy over NLTK/Stanza | Good Dutch support, fast, production-ready |
| SQLite for MVP | Zero setup, sufficient for single user |
| Streamlit for MVP | Rapid iteration, Python-only, familiar from tai8bot |
| Template quizzes first | Reliable, no LLM cost, validates core loop |
| Frequency-based ranking | Recurring words = high-value learning targets |
| Episode-level vocabulary | Granular enough for context, manageable size |

---

## 9. Future Architecture Extensions

- **Spaced repetition** — Replace simple queue with SM-2 or similar
- **Topic clustering** — Group vocabulary by news topic
- **Export to Anki** — Generate Anki decks from saved vocabulary
- **Listening mode** — Audio-only quiz, pronunciation practice
- **CEFR placement** — Estimate user level from known words
