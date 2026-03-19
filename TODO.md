# Dutch News Learner TODO

**Last Updated:** 2026-03-17 (afternoon)

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
- [x] Add Buy Me a Coffee link to Streamlit sidebar
- [x] Fix stale DB on Streamlit Cloud — re-copy on start + 1-hour cache TTL
- [x] Removed `dutch_glosses.json` from git tracking (replaced by SQLite)

---

## Current Status

**Streamlit app** = primary public app (live, fast, reliable)
**Next.js + Vercel** = staging/demo (deployed, looks great, but Render free tier has slow cold starts)

The Next.js frontend is ready for production. The blocker is backend hosting:
Render free tier spins down after 15 min → 30-50s cold starts → bad UX.
To promote Next.js to primary: either pay $7/mo for Render Starter, or migrate to
Phase 6 (Postgres + proper hosting). Not urgent — Streamlit serves well for now.

---

## Pick Up Here (Mar 18)

### Phase 6A: Database Migration to Cloud Postgres (PRIORITY)
Migrate from SQLite-in-git to a cloud Postgres database. This unblocks
automated pipelines and eliminates the growing binary DB in git history.

- [ ] **Choose provider** — Azure Database for Postgres (free tier),
      AWS RDS, Neon, or Supabase. Discuss Mar 18.
- [ ] **Set up cloud Postgres** — create instance, configure access
- [ ] **Update `get_engine()`** — read `DATABASE_URL` env var, keep SQLite fallback for local dev
- [ ] **Adapt `_migrate_schema()`** — Postgres-compatible DDL (some SQLite syntax differs)
- [ ] **Write migration script** — one-time copy: SQLite → Postgres (episodes, vocab, user data, quiz)
- [ ] **Migrate dictionary** — either Postgres table or keep as local SQLite file (read-only, small)
- [ ] **Update secrets** — Streamlit Cloud, Render/Vercel, `.env` for local dev
- [ ] **Test end-to-end** — pipeline writes to Postgres, Streamlit reads from Postgres
- [ ] **Remove `data/dutch_news.db` from git** — add to `.gitignore`

### Phase 6B: GitHub Actions Pipeline Automation
Once DB is on Postgres, the pipeline can run in CI without committing data back to git.

- [ ] **Create `.github/workflows/daily_pipeline.yml`**
      — install Python, deps, spaCy model (cached)
      — run `scripts/run_pipeline.sh`
      — writes directly to cloud Postgres (no git commit needed)
- [ ] **Smart scheduling with retry window:**
      — Weekdays: run every 15 min from 18:00–21:00 UTC (NOS uploads ~18:00,
        sometimes late). Pipeline is idempotent — skips existing episodes, so
        extra runs are harmless and finish fast if nothing new.
      — Weekends: run once at 18:15 UTC (or skip if NOS doesn't upload weekends)
      — Cron: `*/15 18-20 * * 1-5` (weekdays) + `15 18 * * 0,6` (weekends)
- [ ] **Store secrets in GitHub** — `DATABASE_URL`, `YOUTUBE_API_KEY`, `OPENAI_API_KEY`
- [ ] **Add error notifications** — GitHub sends email on failure by default
- [ ] **Test** — trigger workflow manually (`workflow_dispatch`), verify new episode in app
- [ ] **Update `run_pipeline.sh`** — support `DATABASE_URL` env var
- [ ] **Remove cron instructions from README/TODO** — replaced by GitHub Actions

### Phase 6C: Test Suite + CI
Add tests and run them automatically on every push/PR. Catches regressions
before they reach prod and demonstrates CI/CD skills.

- [ ] **Set up pytest** — `tests/` directory, `pytest.ini` or `pyproject.toml` config
- [ ] **Unit tests: quiz generator** — question type selection, distractor picking,
      frequency filter, masking, answer checking. Pure functions, easy to test.
- [ ] **Unit tests: vocabulary processing** — separable verb recombination,
      extraction with known edge cases
- [ ] **Integration tests: FastAPI endpoints** — use `TestClient`, test episode list,
      episode detail, quiz generate/submit, vocabulary status update
- [ ] **DB fixtures** — in-memory SQLite for test isolation (no cloud DB needed)
- [ ] **Create `.github/workflows/test.yml`**
      — trigger: on push to any branch + on pull request
      — install deps, run `pytest --cov` with coverage report
      — fail PR if tests fail
- [ ] **Add coverage badge to README** (optional, nice-to-have)

### Phase 5C: Quiz System (on `quiz-improvements` branch)
Initial quiz code is on main. Improvements (frequency filter, all-MC, English
translations, skip known words) are in progress on a feature branch.
Merge to main when polished.

- [ ] Fix frequency filter — skip words appearing in >30% of episodes (too basic)
- [ ] All questions are MC — cloze uses word options, not text input
- [ ] English-only translations for NL→EN / EN→NL questions (dictionary `gloss_en`)
- [ ] Skip "known" words in episode quiz
- [ ] Session cache invalidation when quiz format changes
- [ ] Consider: integrate frequency list (Subtlex-NL or similar) for CEFR-level targeting
- [ ] Consider: dbt transformation layer for quiz analytics (words learned/week, score trends)

### Backlog

**Transcript & Bubbles:**
- [ ] Merge subtitle segments into sentences (group by punctuation, not by second)
- [ ] Show infinitive/base form in vocabulary bubble when clicked word is conjugated
      (data already exists: `VocabularyItem.lemma`; display change only)
- [ ] Transcript auto-scroll with video playback (high effort)

**Dictionary Quality:**
- [ ] Fill missing `gloss_en` — LLM pass specifically targeting words without English translation
- [ ] Validate dictionary entries — reject garbage (meaning = single inflected form,
      example = just the word itself, e.g. "helftes" → meaning "helft", example "helftes.")
- [ ] Idiom detection + dictionary (Phase 7) — multi-word expressions, spaCy Matcher
      or curated Dutch idiom list. High learning value for users.

**Platform:**
- [ ] Streamlit polish: welcome message, episode count, mobile UX
- [ ] User system: auth, per-user vocabulary tracking
- [ ] Hosting upgrade: promote Next.js to primary, retire Streamlit
- [ ] Analytics: Vercel Analytics, PostHog, learning event tracking

---

## Phase 7: AI Features

- [ ] RAG-based episode search (semantic search with embeddings, pgvector or ChromaDB)
- [ ] AI-generated vocabulary explanations (context-aware, not just dictionary)
- [ ] Personalized difficulty scoring per user
- [ ] Streaming LLM responses in quiz explanations (SSE)

---

## UX Improvements (Backlog)

| Improvement | Impact | Effort | Status |
|-------------|--------|--------|--------|
| ~~Missing translations for inflected forms~~ | Critical | Medium | ✅ Done (LLM enrichment) |
| ~~Separable verb detection (aanvallen, opbellen)~~ | Critical | Medium | ✅ Done (SeparableVerbRecombiner) |
| ~~Video-subtitle sync (click timestamp → seek video)~~ | High | Medium | ✅ Done (postMessage API) |
| Transcript auto-scroll with video playback | High | High | |
| Episode progress indicator ("12 new words") | High | Small | |
| Pronunciation audio (Forvo / Web Speech API) | Medium | Small | |
| Transcript search within episode | Medium | Small | |
| Keyboard shortcuts (arrow keys for episodes, space for play) | Medium | Small | |
| Export to Anki | Medium | Medium | |
| Word frequency across episodes ("seen in 6 episodes") | Medium | Medium | |
| Error boundary for failed API calls (Next.js) | Medium | Small | |
| Loading states / skeleton UI (Next.js) | Medium | Small | |
| Episode navigation — prev/next buttons | Medium | Small | |
| Favicon and Open Graph meta tags | Low | Small | |

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
# Full pipeline (one command) — writes to DATABASE_URL if set, else local SQLite
bash scripts/run_pipeline.sh

# With limits
bash scripts/run_pipeline.sh --max 3

# If still using SQLite: push updated DB for deployments
git add data/dutch_news.db
git commit -m "Update DB with new episodes"
git push origin main

# Once on Postgres + GitHub Actions: pipeline runs automatically, no manual steps
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
| PostgreSQL (Azure/AWS) | Cloud DB migration, connection management |
| CI/CD (GitHub Actions) | Automated daily pipeline, test suite on PR, scheduled workflows |
| Testing (pytest) | Unit + integration tests, DB fixtures, coverage |
| dbt (potential) | Data transformation layer for quiz analytics |
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
- **User testing:** found missing definitions (inflected forms), separable verbs
  not detected, requested video-timestamp seeking
- Revised roadmap: vocabulary quality is top priority (blocks quiz system)
- Added Buy Me a Coffee link to Streamlit sidebar
- Fixed stale DB cache on Streamlit Cloud (re-copy on start + TTL)
- Removed `dutch_glosses.json` from git (replaced by SQLite version)

### Mar 17, 2026
- **Phase 5A: Vocabulary quality** (code + execution)
  - `scripts/enrich_vocab_llm.py` — batch GPT-4o-mini enrichment for words the
    dictionary misses. 25 words/batch, POS + example sentence context. Fills
    `VocabularyItem.translation` for inflected forms, rare words.
  - `SeparableVerbRecombiner` — detects split separable verbs via spaCy dep
    parsing + end-of-clause heuristic. Validates against dictionary to prevent
    false positives. Integrated into VocabularyExtractor.
  - Updated `extract_vocabulary.py` to pass dictionary to extractor.
  - Updated `run_pipeline.sh` from 5 → 7 steps (dictionary + LLM enrichment).
  - Ran all scripts on all episodes — vocabulary quality significantly improved.
- **Phase 5B: Timestamp seeking**
  - Streamlit: transcript component uses `window.parent.document` to find YouTube
    iframe, sends `postMessage` commands (`seekTo` + `playVideo`). Fallback to new tab.
  - Next.js: iframe ref in EpisodeView, `seekTo` callback passed to Transcript.
  - Both: `enablejsapi=1` on embed URL.
- Updated README (roadmap, project structure, tech stack, features, quick start)
- Updated ARCHITECTURE (enrichment chain, separable verbs, data model ERD,
  processing module, API layer, dependencies, design decisions)
- **Phase 5C: Quiz system** — initial implementation shipped to main:
  - DB models: `QuizSession` + `QuizItem` with migrations
  - Generator: `src/quiz/generator.py` — template-based, 3 question types
    (NL→EN, EN→NL, sentence fill-in), episode quiz + daily review
  - Streamlit: Quiz tab on episode page + Daily Review button in sidebar
  - FastAPI: `GET /api/quiz/episode/{id}`, `GET /api/quiz/daily`, `POST /api/quiz/submit`
  - Next.js: `Quiz.tsx` component + API types
- **Quiz user testing** — found issues:
  - Mixed Dutch/English definitions in MC options
  - Cloze (text input) too difficult → should be MC
  - Too many questions (10 → 5)
  - Basic words (vandaag, doen) shouldn't be quizzed
  - Started fixes: frequency filter, all-MC, dictionary gloss_en for English
  - Decision: move quiz improvements to `quiz-improvements` branch
- **Reprioritized roadmap:**
  - Phase 6A (DB migration to cloud Postgres) promoted to top priority
  - Phase 6B (GitHub Actions pipeline) follows immediately after
  - Quiz improvements continue on branch, merge when ready
  - Considering AWS/Azure for Postgres (CV value: Azure, dbt potential)
