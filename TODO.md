# Dutch News Learner TODO

**Last Updated:** 2026-03-20

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

## Pick Up Here (Mar 19)

### Phase 6A: Database Migration to Cloud Postgres ✅ DONE
Migrated from SQLite to Neon Postgres. Pipeline and Streamlit now use `DATABASE_URL`.

- [x] **Choose provider** — Neon (free tier)
- [x] **Set up cloud Postgres** — Neon instance, connection string in `.env`
- [x] **Update `get_engine()`** — reads `DATABASE_URL`, SQLite fallback for local dev
- [x] **Adapt `_migrate_schema()`** — `_pg_add_column` for conditional ALTER, Postgres-compatible DDL
- [x] **Write migration script** — `scripts/migrate_to_postgres.py` (batch inserts, idempotent)
- [x] **Dictionary** — kept as local SQLite (read-only, not migrated)
- [x] **Update secrets** — Streamlit Cloud `DATABASE_URL`, `.env` for local
- [x] **Test end-to-end** — pipeline writes to Postgres, Streamlit reads from Postgres
- [x] **Remove `data/dutch_news.db` from git** — gitignored
- [x] **Lock contention fix** — conditional migrations, `check_locks.py`, `kill_stuck_connections.py`
- [x] **Incremental pipeline** — each step only processes episodes needing it (default)

### Phase 6B: GitHub Actions Pipeline Automation ✅ DONE
Pipeline runs in CI via GitHub Actions. See `docs/GITHUB_ACTIONS_SETUP.md` for details.

- [x] **Create `.github/workflows/daily_pipeline.yml`**
      — Python 3.11, pip cache, spaCy nl_core_news_md
      — Schedule: weekdays */15 18-20 UTC, weekends 18:15 UTC
      — Manual trigger: workflow_dispatch
- [x] **Update `run_pipeline.sh`** — check OPENAI_API_KEY from env or .env (CI-friendly)
- [x] **README/TODO** — note automatic pipeline, de-emphasize cron
- [ ] **Store secrets in GitHub** — `DATABASE_URL`, `YOUTUBE_API_KEY`, `OPENAI_API_KEY` (user action)
- [ ] **Test** — trigger workflow manually, verify new episode in app (user action)

### Per-User Vocabulary — Option A (Quick Fix) ✅ DONE
Implemented localStorage for Next.js so each visitor has their own known/learning status on their device.

- [x] **Next.js: localStorage** — Status stored in browser (`dutch_news_vocab_status`). No API calls for status. User-facing note: "Status saved in this browser — yours alone."
- [x] **Streamlit: stays shared** — Python/server-side cannot access localStorage. Added caption directing users to Next.js for per-device storage. Streamlit Cloud remains shared (user_id=1).
- [ ] **Reddit responses** — User action: post draft replies from `docs/REDDIT_RESPONSE_GUIDE.md`

### Per-User Vocabulary — Phase 6E ✅ DONE, Phase 6F Next
Phase 6E (anonymous sessions) implemented. Preferred UX: Phase 6F (email auth) — no need to explain sessions to users.

- [x] **Phase 6E: Anonymous sessions** — Token in localStorage (Next.js) or URL `?u=<token>` (Streamlit). API `X-Session-Token`, maps to user_id. UserVocabulary per-session.
- [ ] **Phase 6F: Email auth** — Sign up with email; progress saved everywhere. See Phase 6F section below. Branch: `feat/phase-6f-email-auth`.

### Reddit Feedback — Bugs to Fix (This Week)

Posted on r/learndutch; received positive feedback + concrete bug reports. See `docs/REDDIT_RESPONSE_GUIDE.md` for response drafts.

- [x] **Related reading: missing spaces** (Aandeelhouder) — Fixed in `fix_concatenated_spaces()` (Streamlit + Next.js).
- [x] **Vocabulary status buttons: page freeze** (Aandeelhouder) — Addressed: `@st.fragment` + `on_click` + scoped status query (Mar 2026). Re-open if regressions on Streamlit Cloud.
- [ ] **Mobile/Android: empty page** (Humoer) — Streamlit shows empty page on Android browsers. Investigate Streamlit mobile compatibility; consider fallback message or PWA.
- [x] **Filter UX: radio button** (anyalitica) — Replaced checkbox with radio: "Hide known" | "Show all" (Streamlit + Next.js).

### Product Ideas (Reddit + Suggestions) — Prioritization

| Idea | Status | Short-run (This Week) | Long-run |
|------|--------|----------------------|----------|
| Save words to personal review list | ✅ Exists | — | Enhance: dedicated "Review" view, better surfacing |
| Mark episode as done + streak/history | New | — | Add `EpisodeProgress` / streak tracking |
| Mini summary: 1-sentence NL + EN | New | — | LLM: episode summary (Dutch + English); display in header |
| Difficulty labels (episode/sentence) | New | — | CEFR or frequency-based; integrate Subtlex-NL later |
| "Listen first, reveal later" mode | New | — | Hide transcript by default; reveal on click/toggle |
| Daily review from yesterday's words | Partial | Polish quiz to emphasize yesterday's saved words | — |
| Known words storage (per-user) | 6E done | Next.js + Streamlit: anonymous sessions | Phase 6F: email auth (preferred UX) |

**Short-run focus (today–this week):**
1. ~~Fix related reading spaces bug~~ ✅ Done
2. ~~Radio button for hide/show known words~~ ✅ Done
3. ~~Per-user vocab: Option A (localStorage for Next.js)~~ ✅ Done
4. Respond to Reddit comments (user action)
5. Fix vocabulary status freeze (deferred to tomorrow)

**Long-run roadmap adjustments:**
- Add **Episode progress + streak** to backlog (high impact, medium effort)
- Add **Listen first mode** to backlog (high impact, small effort)
- Add **Mini summary** to backlog (medium impact, medium effort — LLM)
- **Mobile UX** moved up: Streamlit polish for mobile, or document limitations

### Phase 6E: Anonymous Sessions ✅ DONE
Upgrade path from Option A (localStorage). Gives per-user vocab with persistence across visits, no login.
Implemented — token in localStorage (Next.js) or URL param (Streamlit). UserVocabulary uses per-session user_id.

### Phase 6F: Email Auth (Per-User Vocabulary — Preferred UX)

**Why:** Users shouldn't need to understand sessions (URL tokens, bookmarking, localStorage). Email signup gives a simple story: "Create account → your progress is saved everywhere." No explaining where data lives.

**Branch:** `feat/phase-6f-email-auth` (create after merging `feat/phase-6e-anonymous-sessions`)

#### Commit 1: Database + models
- [ ] Add `User` table: `id`, `email` (unique, indexed), `password_hash`, `created_at`
- [ ] Add migration: `users` table, `UserVocabulary.user_id` FK to `users.id` (or keep linking via new `user_id` column; `users.id` becomes the user_id for UserVocabulary)
- [ ] Reserve `user_id=1` for legacy/anonymous; `user_id=2+` = registered users. `AnonymousSession` ids can stay separate — migration: when user signs up, copy `AnonymousSession`/legacy UserVocabulary rows to the new `User`'s id, then optionally delete anonymous rows
- [ ] Export `User` from `src.models`

#### Commit 2: Auth backend (FastAPI)
- [ ] Choose auth lib: **FastAPI Users** (https://fastapi-users.github.io) or **Authlib** + JWT, or hand-roll with `passlib` + `python-jose`
- [ ] `POST /api/auth/register` — email + password; hash with bcrypt/argon2; create User; return session token or set cookie
- [ ] `POST /api/auth/login` — email + password; verify; return JWT or set HTTP-only cookie
- [ ] `POST /api/auth/logout` — clear session
- [ ] `GET /api/auth/me` — return current user (email, id) if authenticated
- [ ] Auth dependency: `get_current_user(request) -> User | None`; protect vocab/episode routes — if authenticated, use `user.id`; else fall back to `X-Session-Token` (anonymous) or `user_id=1` (legacy)
- [ ] Add `SECRET_KEY`, `JWT_ALGORITHM` (or similar) to env

#### Commit 3: Next.js auth UI
- [ ] Auth context: `useAuth()` — `user`, `login`, `register`, `logout`, `loading`
- [ ] Login page: `/login` — email + password form, call `POST /api/auth/login`
- [ ] Register page: `/register` — email + password, call `POST /api/auth/register`
- [ ] Header: show "Log in" / "Sign up" when anonymous; show "Log out" + email when authenticated
- [ ] Persist session: JWT in `localStorage` or HTTP-only cookie (cookie is more secure; requires API to set it)
- [ ] Send `Authorization: Bearer <token>` on API requests when logged in; backend prefers Bearer over `X-Session-Token`
- [ ] Migrate anonymous progress: on first login after using app anonymously, offer "Merge your progress?" — call API to copy `AnonymousSession` UserVocabulary to `User` id

#### Commit 4: Streamlit auth (optional)
- [ ] Streamlit has no native auth; options: (a) **Streamlit-Authenticator** (`pip install streamlit-authenticator`), (b) embed login in iframe and pass token via query param, (c) client-side only for Next.js; Streamlit stays anonymous with URL token
- [ ] If supporting Streamlit auth: add login form in sidebar; store JWT in `st.session_state`; send token to API if Streamlit ever calls API directly, or keep Streamlit server-side DB access and use `User` id from session

#### Migration path (anonymous → registered)
- [ ] When user registers: optionally pass `anonymous_token` (or `X-Session-Token`) in request; backend copies `UserVocabulary` rows from anonymous user_id to new User id; delete or leave anonymous rows
- [ ] Document in README: "Sign up to save progress across devices"

#### Security notes
- [ ] Password: min 8 chars; use bcrypt or argon2
- [ ] Rate-limit login/register (e.g. 5 attempts/min per IP)
- [ ] Email verification (optional for MVP): send link to verify; mark `User.email_verified`

### Phase 6D: VPN Integration for Transcript Fetch (Geo-Restriction)
GitHub Actions runners are typically in the US; NOS transcripts may be geo-restricted.
Integrate NordVPN in the workflow so ingest runs from a Netherlands IP.

- [ ] **Add NordVPN step to workflow** — connect to NL server before ingest
- [ ] **Store NordVPN credentials** — add `NORDVPN_SERVICE_USERNAME`, `NORDVPN_SERVICE_PASSWORD` as repo secrets (or use token-based auth if supported)
- [ ] **Wrap ingest in VPN** — run only ingest + transcript fetch steps inside VPN; disconnect before remaining steps
- [ ] **Test** — verify transcript fetch succeeds in CI
- [ ] **Document** — update `docs/GITHUB_ACTIONS_SETUP.md` with VPN setup

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
- [ ] Clickable calendar view for episode selection by date
- [ ] Streamlit polish: welcome message, episode count, mobile UX
- [ ] User system: email auth, per-user vocabulary (Phase 6F)
- [ ] Phase 6E: Anonymous sessions (per-user vocab without auth; upgrade from localStorage)
- [ ] Hosting upgrade: promote Next.js to primary, retire Streamlit
- [ ] Analytics: Vercel Analytics, PostHog, learning event tracking

**Reddit / Product Ideas (new):**
- [ ] Episode progress: mark as done, streak counter, watch history
- [ ] Mini summary: one-sentence Dutch + English per episode (LLM)
- [ ] "Listen first, reveal later" mode — hide transcript by default
- [ ] Difficulty labels per episode (CEFR or frequency-based)

### Vocabulary export + learner notes (`feat/vocab-export-learner-notes`)

High value for active learners: personal sentence/notes per word, then browse and export for spreadsheet or Anki-style review.

#### Done
- [x] **Schema** — Nullable `user_sentence` on `user_vocabulary`; migration in `_migrate_schema` (Postgres + SQLite)
- [x] **API** — `PATCH /api/vocabulary/{id}/note` (required body field `user_sentence`, null/`""` clears, max 2000 chars); `user_sentence` on `GET /vocabulary/status` and `PUT .../status` response
- [x] **Streamlit (episode page)** — Vocabulary expander: learner note text area + **Save note**; caption encourages own sentence/notes (export later)

#### Remaining — API export (foundation) ✅ DONE (commit: GET /vocabulary/export)
- [x] **`GET /api/vocabulary/export`** — Query params: `status` (`new` \| `learning` \| `known` \| `all`), optional `has_note`, `format` (`csv` \| `json`, query name `format`)
- [x] **Column selection** — `columns=comma,separated` allow-list; defaults documented in OpenAPI
- [x] **Row data / joins** — `UserVocabulary` + `VocabularyItem` + dictionary NL/EN; **episode example** = row from **latest episode by `published_at`** (see endpoint docstring)
- [x] **Anki-shaped export** — `template=anki` → `Front` / `Back` / `Tags`; see `docs/ANKI_IMPORT.md`
- [x] **Auth** — `get_user_id` (Bearer / `X-Session-Token` / legacy)

#### Remaining — “My vocabulary” personal page (Streamlit first) ✅ DONE (this commit)
- [x] **New page or section** — Sidebar **Navigate → My vocabulary**; table via preview + downloads
- [x] **Filters** — Status **multiselect** (subset of new / learning / known); learner note (any / with / without); **word** substring search; optional **episode publish date range** (UTC calendar day)
- [x] **Column visibility** — `multiselect` aligned with API export columns (`src/vocab_export.py`)
- [x] **Export actions** — **Download CSV** + **Download Anki CSV** (UTF-8 BOM); Excel = open CSV in Excel for v1
- [x] **Preview** — First 10 rows shown before download
- [ ] **Bulk scope** — Row checkboxes + “export selection only” (follow-up)
- [ ] **Saved presets (later)** — Named column sets, e.g. “Minimal Anki” vs “Full sheet”
- [x] **Episode watch state** — `user_episode_watches` table; Streamlit **Mark episode as watched / not watched**; **My vocabulary** + `GET /vocabulary/export` filter `episode_watch=any|watched_only|unwatched_only`

#### Remaining — Next.js (defer after Streamlit)
- [ ] **Episode vocabulary tab** — Note field + save via `PATCH .../note` (reuse API)
- [ ] **Personal / my vocabulary page** — Same concepts as Streamlit: filters, columns, export (or link to download from API)

#### Later / optional
- [ ] **Native Anki `.apkg`** — Only if CSV import is not enough; higher effort
- [ ] **Cross-episode stats** — e.g. “seen in N episodes” on personal table (separate small feature)

**Branch:** `feat/vocab-export-learner-notes`

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
| Related reading: fix missing spaces in snippets | High | Small | Reddit bug |
| ~~Vocabulary status: fix freeze on click~~ | High | Medium | ✅ Streamlit fragment + on_click (Mar 2026) |
| Mobile/Android: empty page | Medium | TBD | Reddit bug |
| Transcript auto-scroll with video playback | High | High | |
| Episode progress indicator ("12 new words") | High | Small | |
| Pronunciation audio (Forvo / Web Speech API) | Medium | Small | |
| Transcript search within episode | Medium | Small | |
| Keyboard shortcuts (arrow keys for episodes, space for play) | Medium | Small | |
| Export to Anki / spreadsheet | Medium | Medium | In progress — see **Vocabulary export + learner notes** (CSV + Anki-shaped export; personal page) |
| Word frequency across episodes ("seen in 6 episodes") | Medium | Medium | |
| Error boundary for failed API calls (Next.js) | Medium | Small | |
| Loading states / skeleton UI (Next.js) | Medium | Small | |
| Episode navigation — prev/next buttons | Medium | Small | |
| Clickable calendar view for episode selection by date | Medium | Medium | |
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
Runs automatically via GitHub Actions (weekdays 18:00–20:00 UTC, weekends 18:15 UTC).

```bash
# Local run (incremental)
bash scripts/run_pipeline.sh

# Re-process all or limit
bash scripts/run_pipeline.sh --all
bash scripts/run_pipeline.sh --max 3
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

### Mar 18–19, 2026
- **Phase 6A: Postgres migration** (Neon)
  - `get_engine()` reads `DATABASE_URL`, SQLite fallback
  - `_pg_add_column()` for conditional ALTER (avoids lock contention)
  - `migrate_to_postgres.py` — batch inserts, idempotent
  - Streamlit Cloud: removed /tmp copy hack, uses DATABASE_URL
  - Switched to channel uploads playlist (UUch2JvY2ZSwcjf5gb93HGQw)
- **Lock contention fix:** Multiple processes running old ALTER TABLE caused deadlocks.
  - Conditional migrations via information_schema check
  - Pool-level lock_timeout reset on connect
  - `check_locks.py`, `kill_stuck_connections.py` for diagnostics
- **Incremental pipeline:** Each step defaults to "only process what's missing"
  - extract_vocabulary: episodes with no episode_vocabulary
  - translate_segments: episodes with untranslated segments
  - extract_topics: episodes missing topics
  - fetch_related_articles: already incremental

### Mar 19, 2026 (continued)
- **Phase 6B: GitHub Actions**
  - `.github/workflows/daily_pipeline.yml` — scheduled + manual trigger
  - run_pipeline.sh: OPENAI_API_KEY from env or .env (CI-friendly)

### Mar 23, 2026
- **Reddit r/learndutch** — Posted for feedback, ~12h ago
  - Positive reception (Dank je wel, "geweldige tool", "exactly what I was looking for")
  - Bug reports: Related reading missing spaces; vocabulary status buttons cause freeze; Android empty page
  - UX suggestion: radio button for hide/show known words
  - Question: known words storage (currently shared, no auth)
- **Product ideas** — Mapped to TODO: episode done + streak, mini summary, listen-first mode, difficulty labels
- **Prioritization** — Short-run: fix bugs, respond to Reddit; long-run: episode streak, listen-first, mini summary
- **fix/reddit-feedback branch** — Related reading spaces fix, radio button filter
- **Per-user vocab (Option A)** — localStorage for Next.js (per-device); Streamlit stays shared with caption. Future: Phase 6E anonymous sessions.
