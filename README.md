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
- Subtitle transcript with timestamps
- Clickable vocabulary
- Episode summary
- Extracted vocabulary list

**Learning flow:** Open today's episode → watch video → read subtitles → click unknown words → save vocabulary → take daily quiz

### Subtitle-Driven Learning

- Sentence-level subtitle display
- Timestamps linked to video playback
- Clickable vocabulary inside subtitles (click-to-show definition bubble)
- Replay from subtitle timestamps
- Optional English translations per segment (LLM-generated, toggle show/hide)

### Vocabulary Extraction

Automatic extraction of candidate vocabulary from each episode:

- Word form, lemma, translation
- Example sentence, short explanation
- Frequency count, difficulty estimate

Users can mark words as: **known** | **learning** | **saved for review**

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

For each episode, topic keywords are extracted (LLM) and linked to NOS search. Results are filtered to ±2 days around the episode date for more relevant news articles.

### Non-Goals (v1)

To keep the project focused, v1 intentionally avoids:

- Chatbot interfaces
- Conversational tutoring
- Speech recognition
- Complex grammar analysis
- Agent workflows
- Heavy reliance on LLMs (except for optional segment translation and topic extraction)

---

## Tech Stack

### Personal Version (MVP)

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI |
| Database | SQLite |
| NLP | spaCy (nl_core_news_md) |
| Ingestion | youtube-transcript-api, YouTube Data API v3 |
| Frontend | Streamlit |

### Public Platform (Future)

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, PostgreSQL |
| Frontend | Next.js |
| Infrastructure | Docker, background job scheduler |
| Auth | TBD (Auth0 / Supabase) |

---

## Project Structure

```
dutch_news_learner/
├── README.md                 # This file
├── ARCHITECTURE.md            # System design & data flow
├── requirements.txt
├── .env.example
│
├── src/
│   ├── ingestion/             # YouTube & transcript pipeline
│   ├── processing/            # NLP, vocabulary extraction
│   ├── models/                # SQLAlchemy models
│   ├── api/                   # FastAPI routes
│   └── quiz/                  # Quiz generation logic
│
├── scripts/
│   ├── ingest_playlist.py     # Ingest NOS episodes
│   ├── extract_vocabulary.py  # Run NLP pipeline
│   ├── translate_segments.py  # LLM translation (optional)
│   ├── extract_topics.py     # Topic extraction for Related reading
│   ├── download_dictionary.py # Wiktionary nl → Dutch/English glosses
│   └── init_db.py             # Database setup
│
├── app/                       # Streamlit frontend
│   └── main.py
│
├── data/                      # Local data (gitignored)
│   ├── dutch_news.db
│   └── frequency_lists/       # Subtlex-NL, etc.
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

# 2. Configure environment
cp .env.example .env
# Edit .env: YOUTUBE_API_KEY=your_key

# 3. Ingest episodes (uses default playlist: Drie onderwerpen in makkelijke taal)
python scripts/ingest_playlist.py --init-db --max-videos 5

# 4. Extract vocabulary (Phase 2 — requires spaCy Dutch model)
python -m spacy download nl_core_news_md
python scripts/extract_vocabulary.py --max 5

# 5. (Optional) Download dictionary for embedded translations
python scripts/download_dictionary.py   # ~118MB download, one-time. POS-aware for correct meanings.
python scripts/enrich_vocabulary.py     # Populate translations in DB

# 6. (Optional) Segment translation & topic extraction (requires OPENAI_API_KEY)
python scripts/translate_segments.py --max 5   # Translate subtitles to English
python scripts/extract_topics.py --max 5       # Extract topics for Related reading

# 7. Start the learning app
streamlit run app/main.py
```

**Default playlist:** [Drie onderwerpen in makkelijke taal](https://www.youtube.com/playlist?list=PLO72qiQ-gJuFzpCgQcsdd4lkulqeeBMC3) — Dutch news in easy language.

---

## Development Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **1** | Ingestion pipeline (YouTube + transcripts) | ✅ Done |
| **2** | Vocabulary processing (tokenization, lemmatization, frequency) | ✅ Done |
| **3** | Learning interface (episode viewer, clickable vocab, translation toggle) | ✅ Done |
| **3.5** | Related reading (topic extraction, date-filtered NOS links) | ✅ Done |
| **4** | Daily quiz system | Planned |
| **5** | Personalization (known words, ranking, progress) | Planned |
| **6** | Public platform (multi-user, auth, deployment) | Future |

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

**Tanya Yi-En Chen**  
AI Engineer / Data Scientist specializing in data pipelines, NLP systems, and AI applications.
