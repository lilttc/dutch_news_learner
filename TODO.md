# Dutch News Learner TODO

**Last Updated:** 2026-03-15 (end of day)

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
- [x] Buy Me a Coffee link in header (placeholder URL)
- [x] Vercel Analytics wired up (`@vercel/analytics`)
- [x] Vercel deployment config (`vercel.json`)

---

## Your Action Items (manual steps)

- [ ] **Buy Me a Coffee**: Create account at buymeacoffee.com, update URL in `frontend/src/app/layout.tsx`
- [ ] **Cron job**: Set up `crontab -e` with the daily pipeline entry (see below)
- [ ] **Clean up .env**: Remove `GOOGLE_CSE_ID` (no longer used)
- [ ] **Test the Next.js frontend**: Open http://localhost:3000, click through episodes
- [ ] **Push to GitHub**: Commit all changes, push to remote

---

## Phase 5: Polish + Deploy (Next)

The frontend exists but needs polish before going public.

### Frontend Polish
- [ ] Responsive mobile layout testing (Tailwind already responsive, but verify)
- [ ] Video-subtitle sync (click timestamp → seek embedded video via postMessage)
- [ ] Loading states / skeleton UI while API data loads
- [ ] Error boundary for failed API calls
- [ ] Episode navigation (prev/next buttons)
- [ ] Sidebar or header episode search
- [ ] Favicon and Open Graph meta tags for social sharing

### Backend Polish
- [ ] CORS: update allowed origins once Vercel URL is known
- [ ] Episode search endpoint (search by title/topic)
- [ ] Pagination for episode list
- [ ] Rate limiting for vocabulary status updates

### Deployment
- [ ] Push repo to GitHub
- [ ] Deploy Next.js frontend to Vercel (free)
- [ ] Deploy FastAPI backend to Render (free tier) or Railway
- [ ] Set `NEXT_PUBLIC_API_URL` on Vercel to backend URL
- [ ] Verify analytics are collecting data in Vercel dashboard

---

## Phase 6: User System + Analytics

- [ ] Supabase auth (email / Google login)
- [ ] PostgreSQL migration (Supabase or Neon free tier)
- [ ] Per-user vocabulary tracking (replace user_id=1 hardcode)
- [ ] PostHog integration for deeper analytics
- [ ] Learning-specific event tracking (episode views, word lookups)

---

## Phase 7: Quiz System

- [ ] Design quiz question types (translation MC, fill-in-blank, audio)
- [ ] Quiz generation logic (template-based + LLM for distractors)
- [ ] Quiz page in Next.js with timer, progress bar
- [ ] Spaced repetition scheduling (SM-2 or FSRS)
- [ ] Quiz results history and review

---

## Phase 8: AI Features

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

# Terminal 3 (optional): Streamlit (legacy)
streamlit run app/main.py
```

### Daily Pipeline
```bash
# Full pipeline (one command)
bash scripts/run_pipeline.sh

# With limits
bash scripts/run_pipeline.sh --max 3
```

### Cron Setup
```bash
crontab -e
# Run daily at 20:00 (NOS uploads weekdays around 17:00-18:00)
0 20 * * * cd /path/to/dutch_news_learner && bash scripts/run_pipeline.sh >> logs/pipeline.log 2>&1
```

### Dictionary (one-time)
```bash
python scripts/download_dictionary.py      # NL Wiktionary (~118MB)
python scripts/download_dictionary_en.py   # EN Wiktionary Dutch entries
```

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
| PostgreSQL + Supabase | Database + auth (Phase 6) |
| Docker + CI/CD | Deployment automation (Phase 6) |
| RAG / Vector Search | Semantic episode search (Phase 8) |

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
- Vercel Analytics + Buy Me a Coffee placeholder wired up
