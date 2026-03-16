# Dutch News Learner TODO

**Last Updated:** 2026-03-16 (afternoon)

---

## Completed

### Phase 1-3: Core Platform (Mar 14)
- [x] Ingestion pipeline (YouTube + transcripts)
- [x] Vocabulary processing (spaCy nl_core_news_md)
- [x] Episode viewer with embedded video
- [x] Clickable transcript with definition bubbles (no page reload)
- [x] English meanings in bubbles (gloss_en, comparative forms)
- [x] Segment translation (OpenAI, toggle show/hide, default: hide)
- [x] Vocabulary list with search, sort, frequency count
- [x] Dictionary lookup (Wiktionary NL + EN editions)

### Phase 3.5: UX Improvements (Mar 15 AM)
- [x] Tab layout redesign (Transcript | Vocabulary | Related Reading)
- [x] Bubble scroll fix (max-height 60vh, viewport-aware positioning)
- [x] Vocabulary limit (top 20 + "Show all" toggle)
- [x] Dictionary enrichment: EN Wiktionary Dutch entries from kaikki.org
- [x] Related Reading: real NOS article titles via DuckDuckGo search
- [x] Date-filtered search (±7 days around episode date)
- [x] Retry with exponential backoff for rate-limited searches

### Phase 4A: Pipeline + Known Words (Mar 15 PM)
- [x] Pipeline automation script (`scripts/run_pipeline.sh`)
- [x] Known words filter — `UserVocabulary` table (new/learning/known)
- [x] Status buttons in Streamlit Vocabulary tab
- [x] "Hide known words" checkbox (default on)

### Phase 4B: Next.js Migration (Mar 15 PM)
- [x] FastAPI REST API (`src/api/`)
  - `GET /api/episodes` — list with vocab counts
  - `GET /api/episodes/{id}` — detail with segments, vocabulary, articles
  - `GET /api/vocabulary/status` — user word statuses
  - `PUT /api/vocabulary/{id}/status` — update word status
  - `GET /api/health`
- [x] Next.js + TypeScript + Tailwind project (`frontend/`)
- [x] Episode list page (`/`) with thumbnails, dates, topic badges
- [x] Episode detail page (`/episode/[id]`) with tabbed interface
- [x] Clickable transcript with definition popover
- [x] Vocabulary tab with search, sort, hide-known filter, status buttons
- [x] Related reading tab grouped by topic
- [x] Dark mode support (CSS variables + prefers-color-scheme)
- [x] Buy Me a Coffee link in header (`https://buymeacoffee.com/lilttc`)
- [x] Vercel Analytics wired up (`@vercel/analytics`)
- [x] Vercel deployment config (`vercel.json`)

### Phase 4C: Deployment + Cleanup (Mar 15 Evening)
- [x] Anonymized repo (removed personal name/paths from README, TODO, scripts)
- [x] Comprehensive `.gitignore` (root + frontend)
- [x] Pushed to GitHub: `lilttc/dutch_news_learner` (public)
- [x] Streamlit Community Cloud deployment (live)
- [x] SQLite read-only fix for Streamlit Cloud (copy DB to `/tmp/`)
- [x] Mobile bubble responsiveness (`max-width: 90vw`)
- [x] Buy Me a Coffee account created

### Phase 4D: Code Quality + Deployment (Mar 16)
- [x] Fix N+1 query in `list_episodes` — subquery with `func.count`
- [x] Fix DB engine singleton in `deps.py` — avoid recreating engine per request
- [x] Fix CORS wildcard — use `allow_origin_regex` for `*.vercel.app`
- [x] Dictionary: converted 63MB JSON to SQLite for memory-efficient lookups
- [x] Created `requirements-api.txt` (slim deps, excludes spaCy)
- [x] Deployed FastAPI to Render (free tier) — works but cold starts are slow
- [x] Deployed Next.js to Vercel — connected to GitHub, auto-deploys on push
- [x] Segment translations added for latest 5 episodes (OpenAI)

---

## Current Status

**Streamlit app** = primary public app (live, fast, reliable)
**Next.js + Vercel** = staging/demo (deployed, looks great, but Render free tier has slow cold starts)

The Next.js frontend is ready for production. The blocker is backend hosting:
Render free tier spins down after 15 min → 30-50s cold starts → bad UX.
To promote Next.js to primary: either pay $7/mo for Render Starter, or migrate to
Phase 6 (Postgres + proper hosting). Not urgent — Streamlit serves well for now.

---

## Pick Up Here (Mar 16 evening / Mar 17)

### Housekeeping (do first)
- [ ] **Run daily pipeline** when new episode drops: `bash scripts/run_pipeline.sh`
- [ ] **Push updated DB** so Streamlit Cloud + Render get new episodes
- [ ] **Set up cron job** for daily automation (see Quick Reference)

### Recommended next: Quiz System (Phase 5)
The quiz is the highest-value feature for actual learning. Build it in Streamlit
first (the live app), then port to Next.js later.

- [ ] Design quiz question types (translation multiple choice first)
- [ ] Build quiz generation logic (`src/quiz/generator.py`)
  - Pick words from: today's episode + saved "learning" words + previously wrong
  - Generate 3 distractors: same POS, similar frequency
- [ ] Add quiz page to Streamlit app
- [ ] Store results in `QuizSession` + `QuizItem` tables (already in schema)
- [ ] Track quiz performance in `UserVocabulary` (times_correct, times_incorrect)

### Alternative: Streamlit Polish (quick wins)
- [ ] Add welcome message / episode count on homepage
- [ ] Test mobile UX on phone, fix layout issues
- [ ] Video-subtitle sync (click timestamp → seek embedded video)
- [ ] Share with friends, gather feedback

---

## Phase 6: Postgres + Proper Hosting

This phase promotes the Next.js app to production and solves the data-in-git problem.

### Database Migration
- [ ] Set up PostgreSQL (Supabase or Neon free tier)
- [ ] Write migration script: SQLite → Postgres (episodes, vocabulary, user data)
- [ ] Migrate dictionary from SQLite file to Postgres table
- [ ] Update `get_engine()` to read `DATABASE_URL` env var
- [ ] Remove data files from git (dutch_news.db, dutch_glosses.db)

### User System
- [ ] Supabase auth (email / Google login)
- [ ] Per-user vocabulary tracking (replace user_id=1 hardcode)

### Hosting Upgrade
- [ ] Move FastAPI to Render Starter ($7/mo) or Railway — eliminates cold starts
- [ ] Or: rewrite API as Next.js API routes (everything on Vercel, free)
- [ ] Promote Next.js + Vercel as primary public app
- [ ] Retire Streamlit deployment

### Analytics
- [ ] Verify Vercel Analytics collecting data
- [ ] PostHog integration for deeper analytics
- [ ] Learning-specific event tracking (episode views, word lookups)

---

## Phase 7: AI Features

- [ ] RAG-based episode search (semantic search with embeddings, pgvector or ChromaDB)
- [ ] AI-generated vocabulary explanations (context-aware, not just dictionary)
- [ ] Personalized difficulty scoring per user
- [ ] Streaming LLM responses in quiz explanations (SSE)

---

## UX Improvements (Backlog)

| Improvement | Impact | Effort |
|-------------|--------|--------|
| Video-subtitle sync (click timestamp → seek video) | High | Medium |
| Episode progress indicator ("12 new words") | High | Small |
| Pronunciation audio (Forvo / Web Speech API) | Medium | Small |
| Transcript search within episode | Medium | Small |
| Keyboard shortcuts (arrow keys for episodes, space for play) | Medium | Small |
| Export to Anki | Medium | Medium |
| Word frequency across episodes ("seen in 6 episodes") | Medium | Medium |
| Dark/light mode toggle button | Low | Small |
| Error boundary for failed API calls (Next.js) | Medium | Small |
| Loading states / skeleton UI (Next.js) | Medium | Small |
| Episode navigation — prev/next buttons | Medium | Small |
| Favicon and Open Graph meta tags | Low | Small |

---

## Quick Reference

### Start Development
```bash
# Terminal 1: API backend
cd /path/to/dutch_news_learner
uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Next.js frontend
cd /path/to/dutch_news_learner/frontend
npm run dev

# Terminal 3 (optional): Streamlit
streamlit run app/main.py
```

### Daily Pipeline
```bash
# Full pipeline (one command)
bash scripts/run_pipeline.sh

# With limits
bash scripts/run_pipeline.sh --max 3

# After pipeline, push updated DB for deployments
git add data/dutch_news.db
git commit -m "Update DB with new episodes"
git push origin main
```

### Cron Setup
```bash
crontab -e
# Run daily at 20:00 (NOS uploads weekdays around 17:00-18:00)
0 20 * * * cd /path/to/dutch_news_learner && bash scripts/run_pipeline.sh >> logs/pipeline.log 2>&1
```

### Dictionary
```bash
# One-time download
python scripts/download_dictionary.py      # NL Wiktionary (~118MB)
python scripts/download_dictionary_en.py   # EN Wiktionary Dutch entries

# Convert to SQLite (for Render deployment)
python scripts/convert_dictionary_to_sqlite.py
```

### Deployment URLs
- **Streamlit (primary, live)**: check Streamlit Cloud dashboard
- **Next.js (staging)**: dutch-news-learner.vercel.app
- **API (staging)**: dutch-news-learner-api.onrender.com
- **GitHub**: https://github.com/lilttc/dutch_news_learner
- **Buy Me a Coffee**: https://buymeacoffee.com/lilttc

---

## Skills Demonstrated

| Skill | Where in Project |
|-------|------------------|
| Python (FastAPI, SQLAlchemy, spaCy) | Backend API + NLP pipeline |
| Next.js + TypeScript + Tailwind CSS | Frontend application |
| LLM Application Development | Translation, topic extraction (OpenAI) |
| REST API Design | FastAPI endpoints with Pydantic models |
| Database Design + Migrations | SQLAlchemy models, idempotent migrations |
| Web Scraping | DuckDuckGo search with retry/backoff |
| NLP Pipeline | spaCy tokenization, lemmatization, POS tagging |
| Cloud Deployment | Streamlit Cloud, Vercel, Render |
| Performance Optimization | N+1 query fix, dictionary SQLite migration |
| PostgreSQL + Supabase | Database + auth (Phase 6) |
| RAG / Vector Search | Semantic episode search (Phase 7) |

---

## Session Notes

### Mar 14, 2026
- Translation toggle, related reading, topic extraction, documentation

### Mar 15, 2026
- UX: tab layout, bubble fix, vocab limit, dictionary enrichment (EN Wiktionary)
- Related Reading: switched from Google CSE (403 issues) to DuckDuckGo with retry/backoff
- Pipeline automation: `run_pipeline.sh`
- Known words: `UserVocabulary` model + Streamlit UI
- Next.js migration: FastAPI API (5 endpoints), Next.js frontend (8 source files)
- Vercel Analytics + Buy Me a Coffee wired up
- Anonymized repo, pushed to GitHub (public)
- Deployed to Streamlit Community Cloud (fixed read-only SQLite)
- Buy Me a Coffee account: https://buymeacoffee.com/lilttc

### Mar 16, 2026
- Code review + onboarding with senior engineer
- Backend fixes: N+1 query (subquery), engine singleton, CORS regex
- Dictionary: converted 63MB JSON → SQLite for memory-efficient Render deployment
- Created `requirements-api.txt` (excludes spaCy for lighter API deploys)
- Deployed Next.js to Vercel + FastAPI to Render (free tier)
- Lesson learned: Render free tier (512MB RAM, cold starts) not sufficient for
  production — Streamlit remains primary app until Phase 6 (Postgres + paid hosting)
- Added segment translations for latest episodes
- Revised roadmap: quiz system is next priority, Postgres migration deferred
