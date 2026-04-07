# Dutch News Learner TODO

**Last Updated:** 2026-04-03 (user testing session — own dogfooding)

---

## Start Here (new engineer)

**What the app is:** Streamlit app (primary, live on Streamlit Cloud) that ingests NOS Journaal in Makkelijke Taal from YouTube daily, extracts Dutch vocabulary, and lets users track their learning progress. FastAPI + Next.js exist as a secondary/portfolio frontend (currently suspended on Render/Vercel to save cost).

**What is working today:**
- Streamlit app is live and has real users (from r/learndutch)
- Neon Postgres is the database (cloud, free tier)
- Daily pipeline runs via WSL cron on owner's PC (weekdays 18:00 Amsterdam) — see **Handover: scheduled pipeline** for full ops context
- Email auth is fully implemented (Streamlit sidebar + FastAPI + Next.js)
- Per-user vocabulary tracking (anonymous sessions + registered accounts)
- Vocabulary export to CSV / Anki

**Most important next actions (in order):**
1. **feat/semantic-search** — pgvector episode search (next branch, see branch plan below)
2. **Shadowing mode** — auto-pause after each sentence for speaking practice (highest-value learning feature)
3. **Mobile/Android** — investigate empty page bug on Streamlit

**What NOT to touch first:**
- Next.js / FastAPI — suspended, not the priority while the project is hobby-funded
- Phase 7 AI features — premature
- Alembic full migration — works today, not blocking anything

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

**User-facing today:** **Streamlit** is the main public app (live on Streamlit Cloud, fast UX). **Next.js** on Vercel is deployed and polished; promoting it to *primary* for learners is still a **product choice** (see **Production roadmap** → frontend fork), not blocked only by code.

**Backend:** Neon Postgres is in use (Phase 6A). **Render** free tier for FastAPI still implies cold starts (~30–50s) → poor experience if Next is the main client unless you upgrade hosting or accept the delay.

**Next.js:** deployed, useful as a demo / portfolio frontend, but **not** the main product right now. Promoting it to primary would require better backend hosting and more maintenance, which is hard to justify while the project is hobby-funded.

**Engineering priority:** Hardening for the Streamlit user base: auth/session safety, Alembic + tests, **reliable scheduled ingestion** (see **Handover: scheduled pipeline** below — VPS blocked for transcripts; **WSL/home cron** is the current path), Streamlit reliability / mobile UX.

---

## Handover: scheduled pipeline (Mar 2026)

**For the next person:** this section summarizes what we learned and what is running today.

### YouTube / IP (why the VPS path stalled)

- **Playlist metadata** uses **YouTube Data API v3** (`YOUTUBE_API_KEY`) — usually fine from a VPS.
- **Transcripts** use **`youtube_transcript_api`** (unofficial) — **often blocked or throttled from datacenter IPs** (seen on Vultr Amsterdam). Home/residential egress typically works.
- **Implication:** A cheap EU VPS is **not** a reliable host for **full** `ingest_playlist.py` unless you add a **residential proxy** (cost + code/env) or change how captions are fetched.

### What runs today (owner machine)

- **WSL Ubuntu** + user **`crontab`**: weekdays **18:00** with **`CRON_TZ=Europe/Amsterdam`** (same line pattern as before: `cd` → `source .venv` → `source .env` → `check_episode_needed.py` → if `true`, `run_pipeline.sh` → **`logs/pipeline.log`**).
- **Cron must be running:** `/etc/wsl.conf` has a single **`[boot]`** block with **`systemd=true`** and **`command = "systemctl start cron"`**. After a Windows reboot, WSL starts systemd/cron when the distro starts; **PC must be awake** and **not sleeping** at run time.
- **If jobs never fire at “6 pm”:** Ubuntu cron often uses **UTC** and may **ignore** `CRON_TZ` — try **`0 17`** instead of **`0 18`** for **18:00 CET** (winter), or **`0 16`** for **CEST**. Confirm with `grep CRON /var/log/syslog` (inside WSL) or `journalctl -u cron`.
- **`NEED=false`:** cron still runs the **check**; **`run_pipeline.sh`** is skipped — **`pipeline.log`** may not grow; that is normal.

### Repo / server gotchas (save future debugging)

- **`scripts/run_pipeline.sh`:** must be **LF** line endings. Repo has **`.gitattributes`**: `*.sh text eol=lf`. If bash reports `$'\r': command not found`, run: `sed -i 's/\r$//' scripts/run_pipeline.sh`.
- **Ubuntu minimal images:** install **`python3.12-venv`** (or matching `python3-venv`) before **`python3 -m venv .venv`**.
- **`.env` and bash:** one assignment per line, **single-quoted** values: `OPENAI_API_KEY='sk-...'` — prevents “command not found” on `source .env`.

### VPS / billing

- **Vultr (or similar):** **Destroy** the instance to stop charges; **powered off** still bills. Keep the account if you might try again later (e.g. proxy, or **enrichment-only** jobs that never call transcript APIs).

### GitHub Actions

- If **WSL (or home) cron** owns ingestion, **disable or narrow** the **scheduled** `daily_pipeline.yml` job so Neon is not updated **twice** from two schedulers. CI/tests workflows stay as-is.

---

## Production roadmap (near-term)

Goal: move from **solid prototype** to **small production system** — daily ingestion without depending on a laptop, Neon Postgres as source of truth, clear separation between **serving** (API/apps) and **batch** (`scripts/*`).

**Principles**

- **Ingestion host (updated Mar 2026):** **Transcript fetching** (`youtube_transcript_api`) **often fails from datacenter VPS IPs**; playlist API is usually OK. **Preferred for a reliable full pipeline without extra cost:** **`cron` on a machine with residential IP** (e.g. **WSL on your PC** when it is on at the scheduled time). **EU VPS** remains attractive for **non–YouTube-transcript** work or if you adopt a **residential proxy** / different caption strategy. **GitHub-hosted Actions** for live ingest: still optional/backup (IP/geo); use for **tests/deploy** primarily.
- **GitHub Actions:** Use for **tests, lint, deploys**, and optionally **DB migrations** — not as the long-term owner of ingestion unless you revisit with self-hosted runners or VPN (see Phase 6D).
- **Ship order:** Do **not** block production ingestion on a full **job queue** (`ingestion_jobs`, `SKIP LOCKED`, etc.). Run **`check_episode_needed.py` + `scripts/run_pipeline.sh`** on a **reliable host** (today: **WSL/home cron**; VPS only once transcript IP/proxy is solved); add queue tables, locking, and retries only when monolithic runs hurt (failures, overlap, observability).
- **Alembic:** Treat as a **process change**, not only a library — migrations run in deploy/CI **before** new code expects new schema; avoid mutating schema silently on every API boot (`src/api/main.py` + `_migrate_schema` should shrink over time).

**Concrete order of work**

1. **Auth / session safety** — Mandatory `SECRET_KEY` (no dev default in production); remove risky **fallback-to-legacy** on anonymous session errors (`src/api/session.py`); DB **unique** constraint on `(user_id, vocabulary_id)`; tighten `.env.example`; stop swallowing unexpected errors in `_migrate_schema`.
2. **Migrations + tests together** — Introduce **Alembic** and a **small integration test** suite (auth/session, vocab status, episode detail, export) so schema and behavior stop drifting; add `.github/workflows/test.yml` (**CI runs tests only — no live ingestion**).
3. **Scheduled pipeline** — Same as today: `check_episode_needed.py` then `run_pipeline.sh` against Neon. **Host:** WSL/home `cron` (current) **or** VPS **only** if transcript IP issue is solved (proxy / alternate captions). Document timezone (UTC vs `CRON_TZ`).
4. **Deepen worker model (later)** — `pipeline_runs` / `ingestion_jobs`, discover vs process split, `FOR UPDATE SKIP LOCKED`, retries, admin/status view — when pain justifies it.

**Target architecture (when stable)**

| Piece | Role |
|-------|------|
| Neon Postgres | Source of truth |
| FastAPI | Serves prepared data only; no heavy NLP on request |
| Next.js | Secondary demo / portfolio frontend unless budget + usage justify promoting it later |
| Streamlit | Primary user app for now; optimize this path first |
| Home / WSL (or VPS + workaround) | Ingestion worker (`cron` + pipeline scripts); VPS alone failed transcripts in Mar 2026 trial |
| GitHub Actions | Tests + deploy (+ optional migration step), not live ingest |

**Product / architecture forks (decide before big frontend investment)**

- **Frontend:** Keep **Streamlit primary** while the project is hobby-funded and the real users are there. Keep **Next.js secondary / portfolio** unless budget or usage grows enough to justify a promotion later.
- **Anonymous → registered:** **Default recommendation: merge** anonymous `UserVocabulary` into the new account when the user registers/logs in with an optional `anonymous_token` / session header — **explicit** in UX (“we’ll attach progress to this account”) and **idempotent** (safe to call twice; define conflict rule for duplicate rows, e.g. status precedence).

---

## Pick Up Here (Mar 23)

**Ops / ingestion context (Mar 2026):** read **Handover: scheduled pipeline** above first (YouTube transcript vs VPS IP, WSL `cron`, `.gitattributes`, `.env` quoting, disable duplicate GitHub schedule).

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

### Phase 6B: Scheduled pipeline ✅ DONE (GitHub workflow); **production ingest: WSL cron (Mar 2026)**
Workflow exists: GitHub Actions scheduled + manual run. See `docs/GITHUB_ACTIONS_SETUP.md`.

**Mar 2026 reality:** **Vultr EU VPS** was set up; **YouTube transcript API blocked datacenter IP** → full pipeline moved to **WSL on Windows**: user `crontab`, weekdays **18:00 Amsterdam**, `systemctl start cron` via **`wsl.conf` `[boot]`** with **`systemd=true`**. Details and ops notes: **Handover: scheduled pipeline** (top of this file).

- [x] **Create `.github/workflows/daily_pipeline.yml`**
      — Python 3.11, pip cache, spaCy nl_core_news_md
      — Schedule (see workflow YAML; UTC window) + `workflow_dispatch`; `check_episode_needed.py` gate before full install/run
- [x] **Update `run_pipeline.sh`** — check OPENAI_API_KEY from env or .env (CI-friendly)
- [x] **README/TODO** — note automatic pipeline
- [x] **`.gitattributes`** — `*.sh text eol=lf` so `run_pipeline.sh` works on Linux/WSL (Mar 2026)
- [ ] **Store secrets in GitHub** — only if keeping scheduled ingest on Actions: `DATABASE_URL`, `YOUTUBE_API_KEY`, `OPENAI_API_KEY` (user action)
- [ ] **Test** — trigger workflow manually if using Actions for ingest (user action)
- [x] **VPS trial** — Vultr Amsterdam, Ubuntu 24.04, venv, `.env`, cron tested; **transcript IP block** → not used for ingest (destroy instance to save cost)
- [ ] **Try `yt-dlp` for transcript fetching** — replace `youtube_transcript_api` in `scripts/ingest_playlist.py` with `yt-dlp --write-auto-sub`; test from VPS to see if it bypasses datacenter IP block; if it works, VPS becomes viable again for full pipeline
- [x] **Local WSL cron** — weekdays 18:00 Europe/Amsterdam; `logs/pipeline.log`; verify tomorrow / tune UTC hour if needed (user ongoing)
- [ ] **Disable or narrow GA schedule** — now that WSL owns ingest, avoid double-running pipeline against Neon (user action)

### Streamlit-first priorities (actual users)

- [ ] **Streamlit reliability pass** — focus fixes and polish on the app current users actually use
- [ ] **Mobile/Android support** — investigate empty page bug; add fallback message or workaround if needed
- [ ] **Streamlit ops visibility** — simple admin/status view for last pipeline run, latest episode, failed steps
- [ ] **Keep Next.js explicitly secondary** — use for experimentation / portfolio, not as a blocking migration target

### Per-User Vocabulary — Option A (Quick Fix) ✅ DONE
Implemented localStorage for Next.js so each visitor has their own known/learning status on their device.

- [x] **Next.js: localStorage** — Status stored in browser (`dutch_news_vocab_status`). No API calls for status. User-facing note: "Status saved in this browser — yours alone."
- [x] **Streamlit: stays shared** — Python/server-side cannot access localStorage. Added caption directing users to Next.js for per-device storage. Streamlit Cloud remains shared (user_id=1).
- [ ] **Reddit responses** — User action: post draft replies from `docs/REDDIT_RESPONSE_GUIDE.md`

### Auth & per-user vocabulary — 6E ✅ done, 6F next (one checklist)

**Done (6E):** Anonymous sessions — token in localStorage (Next.js) or URL `?u=<token>` (Streamlit); API `X-Session-Token` → `AnonymousSession` → `UserVocabulary` per session.

**Next (6F):** Email auth + registered users — **single detailed checklist** in **Phase 6F** below (DB, FastAPI, Next.js, optional Streamlit). **Product default** for anonymous → registered: **merge** progress (explicit UX, idempotent API) — also stated under **Production roadmap** § forks; implementation tasks live in Phase 6F **Migration path**.

**Near-term client bug (before or with 6F):**
- [ ] **`frontend/src/lib/api.ts` — session bootstrap retry:** If `GET /api/session` fails, **clear `_sessionPromise`** (and handle rejection) so the next call can retry. Today a rejected promise can stay cached and force a full reload.

### User Testing — Apr 3, 2026 (Dogfooding)

Watched today's NOS Journaal in Makkelijke Taal as a user. Found 9 issues (3 UX bugs, 5 vocabulary quality, 1 content quality).

#### UX Bugs

- [x] **Bubble status buttons broken** — Resolved Apr 3. Status buttons cannot work cross-frame (iframe sandbox blocks parent navigation). **Solution:** read-only bubble with full definition, forms, examples, dictionary links, and styled status pills. Status changes stay in the Vocabulary tab. CSS hover tooltips for quick meaning. Surface form search + auto-expand in Vocabulary tab. Full app rerun after status change syncs transcript badges.
- [x] **English translation misaligned with Dutch** — Fixed Apr 4 (branch fix/translation-alignment). Two-part fix: (1) `merge_segments_into_sentences` now always appends `tr` even when empty; (2) root cause was also in `translate_segments.py` — blank lines in API response caused shift; fixed by parsing numbered output by index. Re-translated all episodes with `--force`.
- [x] **Slow toggle for show/hide English translation** — Fixed Apr 4. Moved checkbox into iframe as pure JS toggle — no Streamlit rerun. Translations always rendered (hidden by default), toggled instantly via `display` style.

#### Vocabulary Quality (→ addressed by Vocab QA Agent below)

- [ ] **"zorg voor" identified as only "zorg"** — Fixed preposition verbs (vast voorzetsel) like "zorgen voor" (lead to / take care of) are not recombined. The `SeparableVerbRecombiner` only handles particle verbs (scheidbare werkwoorden), not verb+preposition collocations.
- [ ] **"stemmen" tagged as VERB, should be NOUN** — spaCy POS error: in context "stemmen" = "votes" (noun), not "to vote" (verb). No post-hoc POS correction layer exists.
- [ ] **Idiom "ten slotte" not identified** — Multi-word expressions / fixed phrases are invisible to the per-token pipeline. Already in backlog but now confirmed as real user pain.
- [ ] **"delen" shows wrong meaning** — "delen" = "to share" (verb) in context, but shows "parts" (noun). Same POS → wrong-translation pattern as "stemmen".

#### Vocab QA Agent (new pipeline step — addresses #4/#5/#6/#7)

- [x] **Implement `scripts/qa_vocab_llm.py`** — Done Apr 4 (branch feat/vocab-qa-agent). Pipeline step 8. Uses gpt-4o (default), batch 20 words, structured JSON output. Stores `qa_translation` and `qa_note` (MWE/idiom) on `VocabularyItem`. POS corrections disabled after testing showed unreliable results. Writes structured eval log to `logs/qa_vocab_eval.jsonl`. Supports `--model`, `--episode-id`, `--max`, `--all`, `--dry-run`.
- [x] **Update `run_pipeline.sh`** — Step 8 added. Skipped if no OPENAI_API_KEY.
- [x] **Display layer** — Bubble and vocab tab now prefer `qa_translation` over step-4 translation. MWE notes shown as "Phrase: ...". Dutch Meaning and English fields correctly separated.
- [ ] **Backfill** ⚠️ IN PROGRESS — Episodes 534/535/536 done. Run `python scripts/qa_vocab_llm.py --all` for remaining ~12,700 words (~$16.50).

#### Content Quality

- [x] **Topic extraction too narrow** — Fixed Apr 4 (branch improve/topic-extraction). Prompt now requests 2-5 word descriptive Dutch phrases (e.g. "gaswinning in Groningen"). Re-extracted 20 most recent episodes and re-fetched articles.

#### Priority Order

1. ~~**Bubble status buttons**~~ ✅ Done (Apr 3)
2. ~~**Vocab QA agent**~~ ✅ Done (Apr 4) — backfill still running
3. ~~**Topic extraction prompt**~~ ✅ Done (Apr 4)
4. ~~**Translation alignment**~~ ✅ Done (Apr 4)
5. ~~**Translation toggle performance**~~ ✅ Done (Apr 4)

---

## Pick Up Here (Apr 4, 2026)

**Session summary:** Completed branches `fix/translation-alignment`, `improve/topic-extraction`, and `feat/vocab-qa-agent` (merged). Branch `feat/semantic-search` is next.

### Immediate (before starting next branch)

- [ ] **Finish vocab QA backfill** — Run `python scripts/qa_vocab_llm.py --all` from WSL. ~12,700 words remaining, ~$16.50, uses gpt-4o by default. Episodes 534/535/536 already done. The branch `feat/vocab-qa-agent` is already merged — this is just a data operation.
- [ ] **Fix SQLAlchemy deprecation warning** — `session.query(VocabularyItem).get(word["id"])` in `scripts/qa_vocab_llm.py:293` should be `session.get(VocabularyItem, word["id"])`. Low priority but noisy in logs.

### Next branch: `feat/semantic-search`

pgvector episode search — lets users find episodes by meaning ("find episodes about immigration") rather than keyword. Planned scope:
- Add `pgvector` extension to Neon Postgres
- Embed episode title + description + transcript preview with `text-embedding-3-small`
- Store embeddings on `Episode` table
- New search endpoint / Streamlit UI widget
- Backfill embeddings for existing episodes

### Branch plan (remaining)

| Order | Branch | Scope |
|-------|--------|-------|
| ✅ 1 | `fix/translation-alignment` | Translation alignment + JS toggle |
| ✅ 2 | `improve/topic-extraction` | Better topic phrases |
| ✅ 3 | `feat/vocab-qa-agent` | LLM-as-judge QA pipeline step |
| 4 | `feat/semantic-search` | pgvector episode search |

---

### Reddit Feedback — Bugs to Fix (Mar 2026)

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
| **Shadowing mode** | New | — | Auto-pause after each sentence for speaking practice; auto (timed pause) + manual (button/spacebar) modes; raw subtitle segments preferred over merged sentences for shorter chunks; JS polls YouTube iframe every ~500ms to detect sentence boundaries |
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

### Phase 6F: Email Auth (Per-User Vocabulary — Preferred UX) ✅ MOSTLY DONE

**Why:** Users shouldn’t need to understand sessions (URL tokens, bookmarking, localStorage). Email signup gives a simple story: “Create account → your progress is saved everywhere.” No explaining where data lives. *(Phase 6E anonymous sessions are done — see **Auth & per-user vocabulary** above.)*

#### Commit 1: Database + models ✅ DONE
- [x] Add `User` table: `id`, `email` (unique, indexed), `password_hash`, `created_at` — `src/models/db.py`
- [x] Migration: `users` table via `_migrate_schema`; sequence starts at 1,000,000 to avoid collision with anonymous session ids
- [x] Reserve `user_id=1` for legacy; anonymous sessions get id=2+; registered users get id>=1,000,000
- [x] Export `User` from `src.models`

#### Commit 2: Auth backend (FastAPI) ✅ DONE
- [x] `POST /api/auth/register` — PBKDF2-SHA256 (werkzeug); returns JWT — `src/api/routes/auth.py`
- [x] `POST /api/auth/login` — verify hash; return JWT
- [ ] `POST /api/auth/logout` — not implemented server-side; client removes token from localStorage (acceptable for JWT)
- [x] `GET /api/auth/me` — returns `user_id`, `email`
- [x] Auth dependency: `get_current_user` + `get_current_user_optional` — `src/api/auth.py`
- [x] `SECRET_KEY` required at startup; `ALLOW_INSECURE_DEV_JWT=1` for local dev only
- [x] Rate-limit login/register: 10/minute per IP via `slowapi` — added Mar 2026

#### Commit 3: Next.js auth UI ✅ DONE
- [x] Auth context: `useAuth()` — `user`, `login`, `register`, `logout`, `loading` — `frontend/src/contexts/AuthContext.tsx`
- [x] Login page: `/login` — `frontend/src/app/login/page.tsx`
- [x] Register page: `/register` — `frontend/src/app/register/page.tsx`
- [x] Header: shows “Log in” / “Sign up” when anonymous; email + “Log out” when authenticated — `frontend/src/components/Header.tsx`
- [x] Persist session: JWT in `localStorage`
- [x] Send `Authorization: Bearer <token>` on API requests
- [ ] Merge anonymous progress — not yet implemented (see Migration path below)

#### Commit 4: Streamlit auth ✅ DONE
- [x] Login + register forms in sidebar — `app/main.py` (`_render_sidebar_auth`)
- [x] JWT stored in `st.session_state`; user_id resolved via `_resolve_user_id`

#### Migration path (anonymous → registered) — REMAINING
**Default product choice:** **merge** anonymous progress into the registered account on signup/login.

- [ ] When user registers/logs in: pass anonymous token; backend merges `UserVocabulary` from anonymous `user_id` into registered `user.id`; idempotent (define conflict rule: e.g. keep newest `updated_at`)
- [ ] UX copy: “We’ll attach your saved words to this account”
- [ ] Document in README: “Sign up to save progress across devices”

#### Security notes
- [x] Password: min 8 chars
- [x] Rate-limit login/register: 10/min per IP (slowapi, Mar 2026)
- [ ] Email verification (optional / future): send verification link; mark `User.email_verified`

### Phase 6D: VPN / NL egress (only if ingest still fails by IP)
**If** the pipeline runs on a **NL or nearby EU VPS**, VPN is often unnecessary. Reserve this for **GitHub-hosted** ingest or non-EU hosts where transcript/geo still fails.

GitHub Actions runners are often US-based; NOS transcripts may be geo-restricted — VPN was one workaround.

- [ ] **Add NordVPN step to workflow** — connect to NL server before ingest
- [ ] **Store NordVPN credentials** — add `NORDVPN_SERVICE_USERNAME`, `NORDVPN_SERVICE_PASSWORD` as repo secrets (or use token-based auth if supported)
- [ ] **Wrap ingest in VPN** — run only ingest + transcript fetch steps inside VPN; disconnect before remaining steps
- [ ] **Test** — verify transcript fetch succeeds in CI
- [ ] **Document** — update `docs/GITHUB_ACTIONS_SETUP.md` with VPN setup

### Phase 6C: Alembic + tests + CI (ingestion not in CI)
Bundle **schema migrations** and **tests** so behavior and DB stop drifting. **Alembic** implies a deploy habit: run migrations **before** new API code (not only implicit startup DDL).

- [x] **Add Alembic** — `alembic.ini`, `alembic/env.py`, `baseline_001` empty revision; existing DBs: `alembic stamp baseline_001` once; new DDL in future revisions
- [ ] **Move off startup DDL** — reduce `_migrate_schema` on API boot; API startup verifies DB connectivity only (align with Production roadmap)
- [x] **Set up pytest** — `tests/`, `pytest.ini`, `requirements-dev.txt` (`pytest`, `httpx`, `alembic`)
- [x] **Integration smoke tests** — `TestClient`: health, session, register/login/me, episodes list/404, vocab status + export JSON
- [ ] **Unit tests: quiz generator** — question types, distractors, frequency filter, etc.
- [ ] **Unit tests: vocabulary processing** — separable verbs, extraction edge cases
- [x] **DB isolation for tests** — temp SQLite file + env before app import (`tests/conftest.py`)
- [x] **Create `.github/workflows/test.yml`** — push + PR; `alembic upgrade head` smoke + `pytest`; **no** live ingestion
- [ ] **Add coverage badge to README** (optional)

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
- [ ] Idiom detection + dictionary — multi-word expressions, spaCy Matcher
      or curated Dutch idiom list. High learning value for users. **Confirmed pain point** (Apr 3 dogfooding: "ten slotte", "zorg voor"). Partially addressed by Vocab QA Agent (see User Testing Apr 3).

**Platform:**
- [ ] Clickable calendar view for episode selection by date
- [ ] Streamlit polish: welcome message, episode count, mobile UX (partial: Mar 23 — nav + episode picker + support strip)
- [ ] User system: email auth + merge path (Phase 6F); anonymous sessions (6E) ✅ done
- [ ] Hosting upgrade (later): revisit whether Next.js should become primary only if budget/usage justify it
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
- [x] **Filters** — Status **multiselect** (subset of new / learning / known); learner note (any / with / without); optional **episode publish date range** (UTC calendar day); **episode watched** filter
- [x] **Column visibility** — `multiselect` aligned with API export columns (`src/vocab_export.py`)
- [x] **Export actions** — **Download CSV** + **Download Anki CSV** (UTF-8 BOM); Excel = open CSV in Excel for v1
- [x] **Preview** — First 10 rows shown before download
- [ ] **Bulk scope** — Row checkboxes + “export selection only” (follow-up)
- [ ] **Saved presets (later)** — Named column sets, e.g. “Minimal Anki” vs “Full sheet”
- [x] **Episode watch state** — `user_episode_watches` table; Streamlit **Mark episode as watched / not watched**; **My vocabulary** + `GET /vocabulary/export` filter `episode_watch=any|watched_only|unwatched_only`
- [x] **Choose episode: hide watched** (Mar 23) — Checkbox **Hide episodes I’ve marked as watched** filters the dropdown; `st.rerun()` when watch toggled with filter on so the list stays correct

#### Streamlit UX + performance (same branch, Mar 23)
- [x] **Main-area navigation** — Horizontal **Navigate** (Episodes \| My vocabulary) in the main panel inside `@st.fragment` (Streamlit forbids fragment widgets in `st.sidebar`)
- [x] **Faster “Mark watched”** — Nested `@st.fragment` on episode detail; `ep_watched_ui_*` session keys; `_cached_episode_sidebar_rows()` (`@st.cache_data`, ttl 120s) for lightweight episode list
- [x] **Support strip** — Compact Episodes-only banner: **Coffee** + **Member** links ([BMC](https://buymeacoffee.com/lilttc) + [membership](https://buymeacoffee.com/lilttc/membership)); no duplicate sidebar coffee/member blocks

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
| Export to Anki / spreadsheet | Medium | Medium | ✅ Streamlit: **My vocabulary** + CSV / Anki CSV; API `GET /vocabulary/export`; Next.js UI still deferred |
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
**Preferred production:** small **EU VPS** + `cron` — run `check_episode_needed.py` (optional gate) then `scripts/run_pipeline.sh` against Neon. **GitHub Actions** may still run a scheduled workflow; avoid **two** schedulers writing the same pipeline without intent.

```bash
# Local or VPS (incremental)
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
| CI/CD (GitHub Actions) | Scheduled pipeline (optional/backup), tests on PR; production ingest → VPS + `cron` (see Production roadmap) |
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
- **Per-user vocab (Option A)** — localStorage for Next.js (per-device); Streamlit stays shared with caption. Superseded for API-backed vocab by Phase 6E (anonymous sessions) ✅.

### Mar 24, 2026
- **Production roadmap** — Added section: VPS-first daily ingest vs GitHub-hosted Actions; ship order (auth/session safety → Alembic + tests → VPS cron → job queue later); Alembic as deploy process; Next vs Streamlit fork; anonymous→registered **merge** default (explicit + idempotent). Phase 6B/6C/6D and Quick Reference aligned.

### Mar 25, 2026
- **TODO hygiene** — **Current Status** aligned with Production roadmap (user-facing today vs engineering priority). **Auth section** deduped (one 6E→6F summary + Phase 6F checklist only). Backlog: removed stale “Phase 6E undone.” **Last Updated** 2026-03-25. Explicit item: Next.js **`_sessionPromise`** reset on `/api/session` failure (`frontend/src/lib/api.ts`). Roadmap typo: CI **tests only**, not “tests only for ingestion.”

### Mar 26, 2026
- **Code review session (Claude Code)** — Full review of codebase; project shared on r/learndutch, ~5 real users.
- **Rate limiting added** — `slowapi` on `POST /api/auth/login` + `/api/auth/register` (10/min per IP). New file `src/api/ratelimit.py` to avoid circular import. Added to `requirements-api.txt`.
- **Vultr VPS** — Set up, tested, YouTube transcript API blocked by datacenter IP → destroyed. WSL cron on owner PC is current production ingest path.
- **Ingestion options documented** — Added `yt-dlp` as candidate replacement for `youtube_transcript_api` to TODO (test on VPS before paying for proxy).
- **Windows Task Scheduler** — Discussed as fix for WSL not auto-starting on PC boot; no cron fires without it.
- **Shadowing mode idea** — Designed with user: auto-pause after each sentence for speaking practice; two modes (auto-timed, manual); JS polls YouTube iframe ~500ms; raw subtitle segments preferred over merged sentences. Added to Product Ideas table.
- **Phase 6F checklist updated** — Marked all completed items (DB, FastAPI auth, Next.js auth UI, Streamlit sidebar auth). Remaining: server-side logout endpoint, anonymous→registered progress merge, email verification (optional).
- **TODO restructured** — Added “Start Here” block for new engineers at the top. Updated Last Updated date.

### Apr 3, 2026
- **Dogfooding session** -- Watched today's NOS episode. Found 9 issues across UX, vocabulary quality, and content.
- **Vocab QA Agent designed** -- New LLM-as-judge pipeline step to fix POS errors, wrong translations, and flag MWEs/idioms. Addresses 4 of 9 issues.
- **Fix bubble status buttons** -- Iframe sandbox blocks all cross-frame navigation (target=_top, window.parent.location, postMessage, BroadcastChannel, custom components). Final solution:
  - Read-only JS bubble inside `st.components.v1.html` iframe with full definition, forms, examples, dictionary links
  - Styled status pills (New / 📖 Learning / ✅ Known) with active state highlighted
  - CSS hover tooltips on underlined words for quick meaning peek
  - Status changes remain in the Vocabulary tab (native Streamlit buttons, reliable)
  - Vocabulary search now matches surface forms (e.g. "uitdrukkingsloze" finds "uitdrukkingsloos")
  - Auto-expand expanders when search yields ≤3 results
  - `st.rerun(scope="app")` after status change keeps transcript bubble badges in sync
- **Attempted and abandoned:** Custom Streamlit component (too slow — every click triggered full rerun), two-column layout with right-pane vocab panel (click-to-select didn't sync), BroadcastChannel bridge (blocked by sandbox), direct parent navigation from iframe (blocked by sandbox).

