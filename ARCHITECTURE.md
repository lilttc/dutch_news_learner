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
│   │ YouTube API  │     │ Tokenization │     │  PostgreSQL (Neon)       │   │
│   │ Transcripts  │     │ Lemmatization│     │  Episodes, Vocabulary,   │   │
│   │              │     │ Frequency    │     │  User Progress, Quizzes   │   │
│   └──────────────┘     └──────────────┘     └────────────┬─────────────┘   │
│                                                          │                  │
│                                                          ▼                  │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                     SERVING LAYER                                      │  │
│   │                                                                       │  │
│   │   Streamlit (primary, live)      FastAPI + Next.js (suspended)        │  │
│   │   Hits Postgres directly         REST API for portfolio frontend       │  │
│   │                                                                       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Production Readiness & Cost

- The core ingestion, NLP, and serving layers are implemented and able to run locally with minimal resources.
- Dictionary storage uses SQLite as a low-cost, low-memory offline backend with JSON fallback for developer convenience.
- OpenAI enrichment is optional; the architecture works with dictionary-backed translation only.
- The current serving model is Streamlit-first, with FastAPI and Next.js available as a secondary/demo stack.

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

### 2.3 Separable Verb Recombination

Dutch separable verbs (scheidbare werkwoorden) split in main clauses:
"aanvallen" (to attack) → "Daarom **vallen** ze gebouwen **aan**".

The `SeparableVerbRecombiner` detects these and stores the combined lemma:

```
spaCy Doc (tokenized sentence)
        │
        ├── Strategy 1: Dependency parsing
        │   Tokens with dep label 'svp' / 'compound:prt'
        │   whose head is a VERB → combine particle + verb lemma
        │
        ├── Strategy 2: End-of-clause heuristic
        │   Known particle as last content token before punctuation
        │   + verb earlier in sentence → combine if valid
        │
        └── Validation: combined form must exist as VERB in dictionary
                         (prevents false positives like "op" + "lopen")
                            │
                            ▼
              verb_overrides: {token.i → combined_lemma}
```

### 2.4 Vocabulary Enrichment

Four-tier pipeline fills and validates `VocabularyItem.translation`:

```
Candidate vocabulary (lemma + POS + example sentence)
        │
        ▼
┌───────────────────────────────┐
│ Tier 1: Wiktionary Dictionary │  POS-aware lookup (NL + EN editions)
│ (dutch_glosses.db — SQLite)   │  enrich_vocabulary.py → translation field
│                               │  Covers base forms; free, no API call
└─────────────┬─────────────────┘
              │ words with no English gloss
              ▼
┌───────────────────────────────┐
│ Tier 2: LLM Enrichment        │  GPT-4o-mini, batches of 25
│ (enrich_vocab_llm.py)         │  Uses POS + example sentence for context
│                               │  Fills inflected forms, rare words
└─────────────┬─────────────────┘
              │ all words
              ▼
┌───────────────────────────────┐
│ Tier 3: LLM QA Agent          │  GPT-4o, batches of 20
│ (qa_vocab_llm.py)             │  Reviews translation for correctness
│                               │  Corrections stored in qa_translation,
│                               │  qa_pos, qa_note (display layer prefers
│                               │  these over the original fields)
└─────────────┬─────────────────┘
              │ still no match
              ▼
┌───────────────────────────────┐
│ Tier 4: Manual Lookup Links   │  Mijnwoordenboek, Woorden.org, Wiktionary
│ (shown in definition bubble)  │  User clicks to look up externally
└───────────────────────────────┘
```

### 2.5 Cross-Episode Frequency

```
Episode 1 vocab ──┐
Episode 2 vocab ──┼──▶ Aggregate by lemma
Episode 3 vocab ──┤    → episode_count, total_count
    ...          ──┘    → last_seen_date
                            │
                            ▼
              Recurring vocabulary ranking
```

### 2.6 Optional LLM Enrichment

```
Episode (title, description, transcript)
        │
        ├─────────────────────────────────────┬────────────────────────┐
        │                                     │                        │
        ▼                                     ▼                        ▼
┌───────────────────┐               ┌───────────────────┐   ┌──────────────────┐
│ translate_segments │               │ extract_topics    │   │ qa_vocab_llm     │
│ (GPT-4o-mini)     │               │ (GPT-4o-mini)     │   │ (GPT-4o)         │
│ → SubtitleSegment │               │ → Episode.topics  │   │ → VocabularyItem │
│   .translation_en │               │   (pipe-separated)│   │   .qa_translation│
│   (toggle in UI)  │               └─────────┬─────────┘   │   .qa_pos        │
└───────────────────┘                         │              │   .qa_note       │
                                              ▼              └──────────────────┘
                                    Related reading: DuckDuckGo search
                                    site:nos.nl, date ±7 days
```

---

## 3. Data Model

### 3.1 Entity Relationship Diagram

```
┌──────────────────┐       ┌─────────────────────┐       ┌──────────────────┐
│    Episode       │       │  SubtitleSegment    │       │  VocabularyItem  │
├──────────────────┤       ├─────────────────────┤       ├──────────────────┤
│ id (PK)          │───┐   │ id (PK)             │       │ id (PK)          │
│ video_id         │   │   │ episode_id (FK)      │       │ lemma (unique)    │
│ title            │   └──│ start_time           │       │ pos               │
│ published_at     │      │ duration             │       │ translation       │
│ thumbnail_url    │      │ text                 │       │ qa_translation    │
│ topics           │      │ translation_en       │       │ qa_pos            │
│ related_articles │      └─────────────────────┘       │ qa_note           │
└────────┬─────────┘                                    │ qa_checked        │
         │                                              │ frequency_rank    │
         │                                              │ cefr_level        │
         │                                              └────────┬─────────┘
└────────┬─────────┘                                              │
         │              ┌─────────────────────┐
         │              │ EpisodeVocabulary   │                   │
         └──────────────│ episode_id (FK)     │◀──────────────────┘
                        │ vocabulary_id (FK)  │
                        │ occurrence_count    │
                        │ example_sentence    │
                        │ example_timestamp   │
                        │ surface_forms       │
                        └─────────────────────┘

┌──────────────────┐       ┌─────────────────────┐
│  UserVocabulary  │       │  QuizSession        │
├──────────────────┤       ├─────────────────────┤
│ id (PK)          │       │ id (PK)             │
│ user_id          │       │ user_id             │
│ vocabulary_id(FK)│       │ quiz_date           │
│ status           │       │ score                │
│ created_at       │       │ duration_seconds    │
│ updated_at       │       └──────────┬──────────┘
└──────────────────┘                  │
                           ┌──────────▼──────────┐
  Status: new | learning   │  QuizItem           │
         | known           ├─────────────────────┤
                           │ session_id (FK)     │
                           │ vocabulary_id (FK)  │
                           │ question_type       │
                           │ user_answer         │
                           │ is_correct          │
                           └─────────────────────┘
  (QuizSession + QuizItem are designed but not yet implemented)
```

### 3.2 Table Definitions

| Table | Purpose |
|-------|---------|
| **Episode** | One NOS Journaal video. Stores YouTube metadata, summary, publish date, topics (pipe-separated for Related reading). |
| **SubtitleSegment** | One subtitle line. Text, start/end timestamps, optional translation_en (LLM), links to episode. |
| **VocabularyItem** | Master vocabulary. Lemma, POS, translation, frequency rank, CEFR. QA fields (qa_translation, qa_pos, qa_note, qa_checked) store LLM-reviewed corrections; display layer prefers these over originals. |
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
└── vocabulary.py       # VocabularyExtractor + SeparableVerbRecombiner

src/dictionary/
├── __init__.py
└── lookup.py           # DictionaryLookup (SQLite + JSON backends, POS-aware)
```

### 5.3 API Layer

```
src/api/
├── __init__.py
├── main.py             # FastAPI app + CORS
├── deps.py             # DB engine singleton
└── routes/
    ├── episodes.py     # GET /api/episodes, GET /api/episodes/{id}
    └── vocabulary.py   # GET /api/vocabulary/status, PUT /api/vocabulary/{id}/status
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
| **youtube-transcript-api** | Subtitle extraction | No key required |
| **spaCy nl_core_news_md** | Dutch NLP (tokenize, lemmatize, POS, dep parse) | ~50MB model |
| **Wiktionary NL + EN** | Dictionary (glosses, POS-aware) | Downloaded once, stored as SQLite |
| **OpenAI API (GPT-4o-mini)** | Segment translation, topic extraction, vocab gap-filling | Optional but recommended |
| **OpenAI API (GPT-4o)** | Vocabulary QA agent — reviews and corrects translations | Optional, higher quality |
| **DuckDuckGo (ddgs)** | Related NOS article search | No key required, rate-limited with backoff |

---

## 7. Deployment Considerations

### 7.1 Current Deployment

- **Auth** — Email-based auth implemented (Streamlit sidebar + FastAPI + Next.js)
- **PostgreSQL (Neon)** — Cloud database, shared by Streamlit app and pipeline
- **SQLite fallback** — Local dev when `DATABASE_URL` not set
- **Dictionary** — Local SQLite file (`dutch_glosses.db`, read-only)
- **Streamlit Cloud** — Primary deployment; auto-deploys from `main` branch
- **FastAPI + Next.js** — Secondary/portfolio stack, currently suspended on Render/Vercel
- **Pipeline** — `run_pipeline.sh` runs via WSL cron on owner's PC (weekdays 18:00 Amsterdam)

### 7.2 Public Platform (Future)

- **PostgreSQL** — Already in use (Neon)
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
| Streamlit for MVP | Rapid iteration, Python-only |
| Next.js for public app | Modern UX, Vercel hosting, dark mode |
| Dictionary + LLM fallback | Dictionary covers base forms cheaply; LLM fills inflected/rare words |
| LLM-as-judge QA | GPT-4o reviews translations post-hoc; corrections in separate qa_* fields preserve audit trail |
| Separable verb recombiner | Dep parsing + heuristic + dictionary validation avoids false positives |
| Template quizzes first | Reliable, no LLM cost, validates core loop |
| Frequency-based ranking | Recurring words = high-value learning targets |
| Episode-level vocabulary | Granular enough for context, manageable size |

---

## 9. Future Architecture Extensions

- **Spaced repetition** — Replace simple queue with SM-2 or similar
- **Topic clustering** — Group vocabulary by news topic
- **Shadowing mode** — Auto-pause after each sentence for speaking practice
- **Semantic search** — pgvector episode search by topic/theme
- **Listening mode** — Audio-only quiz, pronunciation practice
- **CEFR placement** — Estimate user level from known words
- **Mobile** — Investigate empty page bug on Android/Streamlit
