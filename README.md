# Dutch News Learner 🇳🇱

A personal-first Dutch learning platform built from daily news videos.

Dutch News Learner ingests **NOS Journaal in Makkelijke Taal** episodes from YouTube, extracts subtitles, and transforms them into a structured learning environment with personalized vocabulary tracking, recurring word detection, and daily quizzes.

The project begins as a personal learning tool and is designed to evolve into a public language-learning platform.

## Current Status

- **Streamlit is the primary public app today.** It is live on Streamlit Community Cloud and is the main learning experience for users. A migration to a faster, always-on hosted frontend (Next.js) is the next major piece of work — see the roadmap.
- **Next.js + FastAPI exist as a secondary frontend stack** and are the candidate for that migration. This path is implemented but not yet at feature parity with the Streamlit app.
- **Content source:** one channel today — *NOS Journaal in Makkelijke Taal*. Support for additional Dutch channels (e.g. Nieuwsuur, NCRV documentaries) as an opt-in, difficulty-tagged tier is planned.
- **Pipeline and database:** Neon Postgres is the source of truth. The daily pipeline (`scripts/run_pipeline.sh`) runs via CLI, scheduled with Windows Task Scheduler, on the owner's PC — a residential IP is required since YouTube blocks transcript fetching from datacenter hosts.
- **Low-cost operation:** Local SQLite is used for dictionary lookups, OpenAI enrichment is optional, and deployments are kept lightweight by design.

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

- Click-to-watch video card (links out to YouTube — NOS disables third-party embedding)
- Subtitle transcript with clickable timestamps (opens the video on YouTube at that time)
- Clickable vocabulary with definition pop-ups
- Extracted vocabulary list with status tracking

**Learning flow:** Open today's episode → read subtitles (watch the video on YouTube alongside) → click unknown words → save vocabulary → take daily quiz

### Subtitle-Driven Learning

- Sentence-level subtitle display (merges fragmented auto-captions into full sentences)
- Clickable timestamps open the video on YouTube at that point
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

Four-tier translation pipeline ensures high coverage and quality:

1. **Wiktionary dictionary** (NL + EN editions, stored as SQLite) - covers base forms, free
2. **LLM gap-fill** (GPT-4o-mini) - fills missing translations for inflected forms and rare words
3. **LLM QA agent** (GPT-4o) - reviews all translations, corrects errors, flags multi-word expressions
4. **Manual lookup links** (Mijnwoordenboek, Woorden.org, Wiktionary) - shown in the definition bubble

### Personal Vocabulary Tracker

For each word the system tracks:

- First seen date, last reviewed date
- Number of occurrences
- Number of episodes containing the word
- Learning status
- Quiz performance

### Word Frequency Across Episodes

Track how often words appear across multiple news episodes:

> **inflatie** - Seen in 6 episodes · Seen 14 times · Last seen: 2026-03-12

Recurring vocabulary highlights important real-world words.

### Episode Archive

Episodes indexed by date with calendar-style browsing to revisit older episodes and review vocabulary from specific days.

### Related Reading

For each episode, topic keywords are extracted (LLM) and linked to NOS articles via DuckDuckGo search. Results are filtered to ±7 days around the episode date for relevance.

### Ask the News (Semantic Search + RAG)

Episodes are embedded (`text-embedding-3-small`, pgvector) so you can ask a question in plain language and get an answer grounded in the most relevant episodes, with citations back to the specific episode(s) used. Requires Postgres + pgvector — unavailable on the local SQLite dev fallback.

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
| Database | PostgreSQL (Neon) + pgvector + SQLite (dictionary) |
| NLP | spaCy (nl_core_news_md), separable verb recombination |
| Dictionary | Wiktionary NL + EN editions (POS-aware, SQLite) |
| LLM | OpenAI GPT-4o-mini (segment translation, topic extraction, vocab gap-fill) + GPT-4o (vocab QA, RAG answers) |
| Embeddings | OpenAI text-embedding-3-small (semantic episode search) |
| Ingestion | youtube-transcript-api, YouTube Data API v3 |
| Search | DuckDuckGo (related NOS articles), pgvector (semantic episode search) |
| Frontend (primary, live) | Streamlit — migration to Next.js planned |
| Frontend (in progress) | Next.js + TypeScript + Tailwind CSS |

### Public Platform (Future)

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, PostgreSQL |
| Frontend | Next.js |
| Infrastructure | Docker, background job scheduler |
| Auth | TBD (Supabase) |

---

## Cost-efficient design

- Uses open-source tools and free tiers where possible.
- `sqlite` dictionary fallback works offline without additional hosting cost.
- OpenAI enrichment is optional and only used for missing translations.
- Staging demo can run on low-cost cloud services or locally with minimal resources.

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
│   ├── rag.py                          # Shared semantic search + RAG logic (search, answer_question)
│   └── api/                            # FastAPI REST API
│       ├── main.py                     # App + CORS
│       ├── deps.py                     # DB engine singleton
│       └── routes/                     # episodes, vocabulary endpoints
│
├── scripts/
│   ├── run_pipeline.sh                 # Daily pipeline (9 steps, one command)
│   ├── ingest_playlist.py              # Ingest NOS episodes from YouTube
│   ├── extract_vocabulary.py           # spaCy NLP + separable verb detection
│   ├── enrich_vocabulary.py            # Dictionary-based translation fill
│   ├── enrich_vocab_llm.py             # LLM fallback for missing translations
│   ├── translate_segments.py           # Segment translation (OpenAI)
│   ├── extract_topics.py              # Topic extraction (OpenAI)
│   ├── qa_vocab_llm.py                 # LLM-as-judge vocab QA (GPT-4o)
│   ├── fetch_related_articles.py       # DuckDuckGo NOS article search
│   ├── embed_episodes.py               # Embed episodes for semantic search (OpenAI + pgvector)
│   ├── run_eval.py                     # Retrieval evaluation against a hand-labeled Q&A set
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
pip install -r requirements.txt -r requirements-dev.txt
python -m spacy download nl_core_news_md

# 2. Configure environment
cp .env.example .env
# Edit .env: DATABASE_URL (Neon Postgres or local SQLite), YOUTUBE_API_KEY, OPENAI_API_KEY (optional)

# 3. Download or build dictionary (one-time)
python scripts/download_dictionary.py
python scripts/download_dictionary_en.py
python scripts/convert_dictionary_to_sqlite.py

# 4. Ingest episodes
python scripts/ingest_playlist.py --init-db --max-videos 5

# 5. Extract vocabulary (with separable verb detection)
python scripts/extract_vocabulary.py

# 6. Enrich translations (dictionary first, then optional LLM fallback)
python scripts/enrich_vocabulary.py
python scripts/enrich_vocab_llm.py --all   # Requires OPENAI_API_KEY

# 7. (Optional) Segment translation, topic extraction & vocab QA
python scripts/translate_segments.py
python scripts/extract_topics.py
python scripts/qa_vocab_llm.py             # Requires OPENAI_API_KEY

# 8. Start the learning app
streamlit run app/main.py

# Or: Start the Next.js frontend + FastAPI backend
uvicorn src.api.main:app --port 8000 &
cd frontend && npm run dev
```

### Testing

```bash
pytest tests
```

**Source:** NOS Journaal in Makkelijke Taal channel uploads - Dutch news in easy language.

---

## Pipeline Scheduling

The daily pipeline (`scripts/run_pipeline.sh`) is a plain CLI script — run it by
hand, or schedule it. It needs a residential/home IP (YouTube blocks transcript
fetching from datacenter IPs), so it runs on the owner's PC rather than a cloud
scheduler.

### Running manually

```bash
bash scripts/run_pipeline.sh            # Incremental (only new/missing data)
```

### Scheduling via Windows Task Scheduler (WSL)

1. Open **Task Scheduler** → **Create Basic Task**
2. Trigger: **Daily**, weekdays, at the desired time (e.g. 18:00)
3. Action: **Start a program**
   - Program/script: `wsl.exe`
   - Arguments: `bash -lc "cd /home/tchen/dutch_news_learner && bash scripts/run_pipeline.sh >> logs/pipeline.log 2>&1"`
4. Under **Conditions**, uncheck "Start the task only if the computer is on AC power"
   if running on a laptop, so it still fires on battery
5. Save, then test with **Run** in Task Scheduler to confirm it completes and
   `logs/pipeline.log` is updated

---

## Development Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **1** | Ingestion pipeline (YouTube + transcripts) | ✅ Done |
| **2** | Vocabulary processing (tokenization, lemmatization, frequency) | ✅ Done |
| **3** | Learning interface (episode viewer, clickable vocab, translation toggle) | ✅ Done |
| **3.5** | Related reading (topic extraction, date-filtered NOS links) | ✅ Done |
| **4** | Next.js + FastAPI migration, deployment (Vercel + Render + Streamlit Cloud) | ✅ Done |
| **5A** | Vocabulary quality (LLM enrichment, separable verb detection, QA agent) | ✅ Done |
| **5B** | Video-transcript UX (click-to-watch card + timestamp deep links; NOS disabled third-party embedding) | ✅ Done |
| **6A** | PostgreSQL (Neon) + cloud migration | ✅ Done |
| **6B** | Daily pipeline (CLI + Windows Task Scheduler) | ✅ Done |
| **6C** | User auth (email + anonymous sessions) | ✅ Done |
| **7** | Semantic episode search + RAG ("Ask the news", pgvector + GPT-4o) | In progress — scaffolded; needs pgvector enabled on Neon + evaluation |
| **8** | Multi-source ingestion (Nieuwsuur, NCRV, …) + in-app video where embedding is allowed | Planned |
| **9** | Replace Streamlit with a faster hosted frontend (Next.js) | Planned |
| **10** | Spaced repetition (SM-2) | Planned |
| **11** | Pronunciation + shadowing | Needs redesign — assumed in-page video control; possible again on channels that allow embedding |
| **12** | Retention: streaks, progress stats, habit features | Planned |
| **13** | Content quality + CEFR levels | Planned |
| **14** | Multi-language (French via RFI Journal en français facile) | Planned — after 10–12 |
| — | Quiz system (translation multiple choice) | Partially built (Streamlit); expands with Phase 10 |

---

## Copyright & Content Strategy

Videos remain hosted on YouTube; the app links out to watch them there (NOS disables third-party embedding). The application stores only:

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
