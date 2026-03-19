# Dutch News Learner 🇳🇱

A personal-first Dutch learning platform built from daily news videos.

Dutch News Learner ingests **NOS Journaal in Makkelijke Taal** episodes from YouTube, extracts subtitles, and transforms them into a structured learning environment with personalized vocabulary tracking, recurring word detection, and daily quizzes.

The project begins as a personal learning tool and is designed to evolve into a public language-learning platform.

---

## Why This Project?

Traditional language-learning apps rely on artificial sentences and curated exercises. Real fluency requires exposure to **authentic content**.

**NOS Journaal in Makkelijke Taal** is ideal for learners because it provides:

- Real-world Dutch
- Simplified language (Makkelijke Taal = Easy Language)
- Recurring vocabulary
- Consistent daily publishing
- Relevant modern topics

This project transforms those broadcasts into a structured learning workflow:

```
Watch today's episode → Read subtitles → Identify unknown words → Save vocabulary
        → Review with daily quizzes → Track recurring vocabulary
```

The goal is to help learners acquire real-world Dutch vocabulary through repeated exposure.

---

## Core Features

### Daily Episode Page

The homepage displays the latest news episode and acts as the main learning entrypoint.

- Embedded YouTube video
- Subtitle transcript with clickable timestamps (seeks video in-page)
- Clickable vocabulary with definition pop-ups
- Extracted vocabulary list with status tracking

**Learning flow:** Open today's episode → watch video → read subtitles → click unknown words → save vocabulary → take daily quiz

### Subtitle-Driven Learning

- Sentence-level subtitle display
- Clickable timestamps seek the embedded video (no new tab)
- Clickable vocabulary inside subtitles (click-to-show definition bubble)
- Optional English translations per segment (LLM-generated, toggle show/hide)

### Vocabulary Extraction

Automatic extraction of candidate vocabulary from each episode:

- Word form, lemma, translation
- Example sentence from episode context
- Frequency count per episode
- Separable verb recombination (e.g. "vallen ... aan" → "aanvallen")

Users can mark words as: **known** | **learning** | **new**

### Vocabulary Enrichment

Three-tier translation pipeline ensures high coverage:

1. **Wiktionary dictionary** (NL + EN editions, stored as SQLite) — covers base forms
2. **LLM fallback** (GPT-4o-mini) — fills gaps for inflected forms, rare words
3. **Manual lookup links** (Mijnwoordenboek, Woorden.org, Wiktionary)

### Personal Vocabulary Tracker

For each word the system tracks:

- First seen date, last reviewed date
- Number of occurrences
- Number of episodes containing the word
- Learning status
- Quiz performance

### Word Frequency Across Episodes

Track how often words appear across multiple news episodes:

> **inflatie** — Seen in 6 episodes · Seen 14 times · Last seen: 2026-03-12

Recurring vocabulary highlights important real-world words.

### Daily Vocabulary Quiz

Quiz questions generated from:

- New words from the latest episode
- Saved vocabulary
- Frequently recurring words
- Previously incorrect answers

Example: *What does "maatregel" mean?* → A. election · B. measure · C. village · D. warning

### Episode Archive

Episodes indexed by date with calendar-style browsing to revisit older episodes and review vocabulary from specific days.

### Related Reading

For each episode, topic keywords are extracted (LLM) and linked to NOS articles via DuckDuckGo search. Results are filtered to ±7 days around the episode date for relevance.

### Non-Goals (v1)

To keep the project focused, v1 intentionally avoids:

- Chatbot interfaces
- Conversational tutoring
- Speech recognition
- Complex grammar analysis
- Agent workflows

---

## Tech Stack

### Current Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI |
| Database | PostgreSQL (Neon) + SQLite (dictionary) |
| NLP | spaCy (nl_core_news_md), separable verb recombination |
| Dictionary | Wiktionary NL + EN editions (POS-aware, SQLite) |
| LLM | OpenAI GPT-4o-mini (translation, topic extraction, vocab enrichment) |
| Ingestion | youtube-transcript-api, YouTube Data API v3 |
| Search | DuckDuckGo (related NOS articles) |
| Frontend (primary) | Streamlit |
| Frontend (staging) | Next.js + TypeScript + Tailwind CSS |

### Public Platform (Future)

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, PostgreSQL |
| Frontend | Next.js |
| Infrastructure | Docker, background job scheduler |
| Auth | TBD (Supabase) |

---

## Project Structure

```
dutch_news_learner/
├── README.md                          # This file
├── ARCHITECTURE.md                     # System design & data flow
├── TODO.md                             # Development log & roadmap
├── requirements.txt                    # Full dependencies (incl. spaCy)
├── requirements-api.txt                # Slim API deps (no spaCy, for Render)
├── .env.example
│
├── src/
│   ├── ingestion/                      # YouTube & transcript pipeline
│   │   └── youtube.py                  # Playlist + transcript fetchers
│   ├── processing/                     # NLP pipeline
│   │   └── vocabulary.py               # VocabularyExtractor + SeparableVerbRecombiner
│   ├── dictionary/                     # Wiktionary lookup (SQLite + JSON backends)
│   │   └── lookup.py                   # DictionaryLookup (POS-aware, EN glosses)
│   ├── models/                         # SQLAlchemy models
│   │   └── db.py                       # Episode, SubtitleSegment, VocabularyItem, etc.
│   └── api/                            # FastAPI REST API
│       ├── main.py                     # App + CORS
│       ├── deps.py                     # DB engine singleton
│       └── routes/                     # episodes, vocabulary endpoints
│
├── scripts/
│   ├── run_pipeline.sh                 # Daily pipeline (7 steps, one command)
│   ├── ingest_playlist.py              # Ingest NOS episodes from YouTube
│   ├── extract_vocabulary.py           # spaCy NLP + separable verb detection
│   ├── enrich_vocabulary.py            # Dictionary-based translation fill
│   ├── enrich_vocab_llm.py             # LLM fallback for missing translations
│   ├── translate_segments.py           # Segment translation (OpenAI)
│   ├── extract_topics.py              # Topic extraction (OpenAI)
│   ├── fetch_related_articles.py       # DuckDuckGo NOS article search
│   ├── download_dictionary.py          # NL Wiktionary download
│   ├── download_dictionary_en.py       # EN Wiktionary Dutch entries
│   ├── convert_dictionary_to_sqlite.py # JSON → SQLite dictionary conversion
│   ├── migrate_to_postgres.py          # One-time SQLite → Postgres migration
│   ├── check_locks.py                  # Postgres lock diagnostics (manual)
│   ├── kill_stuck_connections.py      # Terminate stuck backends (manual)
│   └── query_db.py                     # Database inspection utility
│
├── app/                                # Streamlit frontend (primary)
│   └── main.py
│
├── frontend/                           # Next.js frontend (staging)
│   ├── src/app/                        # Pages (episode list, episode detail)
│   └── src/components/                 # EpisodeView, Transcript, VocabularyList
│
├── data/                               # Local data (gitignored)
│   ├── dutch_news.db                   # SQLite fallback (local dev)
│   └── dictionary/dutch_glosses.db     # Wiktionary dictionary (SQLite)
│
└── tests/
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- YouTube Data API key
- (Optional) OpenAI API key for translation enrichment

### Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
python -m spacy download nl_core_news_md

# 2. Configure environment
cp .env.example .env
# Edit .env: DATABASE_URL (Neon Postgres), YOUTUBE_API_KEY, OPENAI_API_KEY (optional)

# 3. Download dictionary (one-time, ~118MB)
python scripts/download_dictionary.py
python scripts/download_dictionary_en.py
python scripts/convert_dictionary_to_sqlite.py

# 4. Ingest episodes
python scripts/ingest_playlist.py --init-db --max-videos 5

# 5. Extract vocabulary (with separable verb detection)
python scripts/extract_vocabulary.py   # Incremental: only episodes missing vocabulary

# 6. Enrich translations (dictionary first, then LLM for gaps)
python scripts/enrich_vocabulary.py
python scripts/enrich_vocab_llm.py --all   # Requires OPENAI_API_KEY

# 7. (Optional) Segment translation & topic extraction
python scripts/translate_segments.py
python scripts/extract_topics.py

# 8. Start the learning app
streamlit run app/main.py

# Or: Start the Next.js frontend + FastAPI backend
uvicorn src.api.main:app --port 8000 &
cd frontend && npm run dev
```

### Daily Pipeline

```bash
# Process new episodes (incremental: only what's missing)
bash scripts/run_pipeline.sh

# Re-process all or limit scope
bash scripts/run_pipeline.sh --all      # Re-process everything
bash scripts/run_pipeline.sh --max 5   # Limit to 5 newest per step

# Local cron (alternative to GitHub Actions)
# 0 20 * * * cd /path/to/dutch_news_learner && bash scripts/run_pipeline.sh >> logs/pipeline.log 2>&1
```

**Source:** NOS Journaal in Makkelijke Taal channel uploads — Dutch news in easy language.

---

## Development Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **1** | Ingestion pipeline (YouTube + transcripts) | ✅ Done |
| **2** | Vocabulary processing (tokenization, lemmatization, frequency) | ✅ Done |
| **3** | Learning interface (episode viewer, clickable vocab, translation toggle) | ✅ Done |
| **3.5** | Related reading (topic extraction, date-filtered NOS links) | ✅ Done |
| **4** | Next.js + FastAPI migration, deployment (Vercel + Render + Streamlit Cloud) | ✅ Done |
| **5A** | Vocabulary quality (LLM enrichment, separable verb detection) | ✅ Done |
| **5B** | Video-transcript UX (in-page timestamp seeking) | ✅ Done |
| **5C** | Quiz system (translation multiple choice, spaced repetition) | Up next |
| **6A** | PostgreSQL (Neon) + cloud migration | ✅ Done |
| **6B** | GitHub Actions daily pipeline | Planned |
| **6C** | User auth + proper hosting | Planned |
| **7** | AI features (RAG search, AI explanations) | Future |

---

## Copyright & Content Strategy

Videos are embedded from YouTube and remain hosted on the original platform. The application stores only:

- Metadata
- Processed vocabulary
- Learning annotations

It does not redistribute full subtitle datasets or video content. All episodes link back to the original source.

---

## License

MIT

---

## Author

**[@lilttc](https://github.com/lilttc)**
