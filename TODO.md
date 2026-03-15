# 📋 Dutch News Learner TODO

**Last Updated:** 2026-03-14 — Related reading, translation toggle, docs updated ✅

---

## 🎯 Tomorrow's Plan (Mar 15) — Optional Polish

### Priority 1: Data & Testing
1. **Run extract_topics on all episodes** (if not done)
   ```bash
   python scripts/extract_topics.py --all
   ```
2. **Verify Related reading links** — Check date-filtered Google search works
3. **Test full flow** — Ingest → Extract vocab → Translate → Extract topics → App

### Priority 2: Documentation
- [ ] Add README section on dictionary fallback (gloss_en)
- [ ] Document .env variables in .env.example

### Priority 3: Next Feature Prep
- [ ] Review quiz requirements (Phase 4)
- [ ] Sketch quiz data model (QuizSession, QuizItem)

---

## 📅 This Week's Plan (Mar 15–19)

### Mar 15–16: Quiz Foundation
- [ ] Design quiz question types (translation MC, fill-in-blank)
- [ ] Create QuizSession, QuizItem tables (if not in schema)
- [ ] Build quiz generation logic (template-based, no LLM)

### Mar 17–18: Quiz UI
- [ ] Add quiz page/section to Streamlit app
- [ ] Pool: new words from episode + saved vocabulary
- [ ] Record results, update UserVocabulary

### Mar 19: Polish & Testing
- [ ] End-to-end testing
- [ ] Fix edge cases
- [ ] Update docs

---

## 🎯 Completed Today (Mar 14, 2026) ✅

### 1. **Translation Toggle Default**
- [X] Changed "Show English translation" checkbox default to `value=False` (hide by default)

### 2. **Related Reading Feature** 📰
- [X] Added `Episode.topics` column (pipe-separated: "topic1|topic2|topic3")
- [X] Created `scripts/extract_topics.py` — LLM extracts 3 topic keywords from title + description + transcript preview
- [X] Migration for `topics` in `_migrate_schema`
- [X] Related reading section in app — links to NOS articles per topic
- [X] Date-filtered search: Google `site:nos.nl` with `tbs=cdr:1,cd_min:...,cd_max:...` (±2 days around episode date)
- [X] Caption indicates when results are date-filtered

### 3. **Documentation**
- [X] Updated README — Related reading, new scripts, quick start steps
- [X] Updated ARCHITECTURE — Episode.topics, SubtitleSegment.translation_en, LLM enrichment pipeline
- [X] Created TODO.md (this file)

---

## 🎨 UX Suggestions for Learners

### High impact

| Improvement | Why | Status |
|-------------|-----|--------|
| **Clickable words → scroll to vocab card** | Click a word in the transcript → scroll to and expand its vocabulary card. Reduces searching. | ⏳ Partial: we have click-to-show bubble; add scroll-to-card |
| **Mark as known / learning** | Let users mark words (known / learning / ignore) and optionally hide known words so the list focuses on new vocabulary. | Planned |
| **Episode progress** | Show "X of Y words" or "3 new words today" to give a sense of progress. | Planned |

### Medium impact

| Improvement | Why | Status |
|-------------|-----|--------|
| **Video–subtitle sync** | When clicking a timestamp, seek the embedded video to that time instead of opening YouTube in a new tab. | Planned |
| **Pronunciation link** | Add a link to Forvo or similar for audio pronunciation. | Planned |
| **Transcript search** | Search box to find a word or phrase in the transcript. | Planned |

### Nice to have

| Improvement | Why | Status |
|-------------|-----|--------|
| **Export to Anki** | Export selected vocabulary as an Anki deck. | Future |
| **Dark mode** | Toggle for dark theme. | Future |
| **Mobile layout** | Better layout on phones and tablets. | Future |

### Suggested implementation order

1. **Clickable words → scroll to vocab card** — biggest usability gain (enhance existing)
2. **Mark as known** — supports personalization and focus
3. **Video–subtitle sync** — keeps everything in one place

---

## 🚀 Long-Term Roadmap

### Phase 4: Daily Quiz (Next)
- [ ] Quiz question generation (template-based)
- [ ] Quiz UI in Streamlit
- [ ] UserVocabulary status (known / learning / ignored)
- [ ] Track quiz performance

### Phase 5: Personalization & UX
- [ ] UserVocabulary persistence (mark as known / learning / ignore)
- [ ] Known words filter (hide known words)
- [ ] Episode progress ("X of Y words", "3 new words today")
- [ ] Clickable words → scroll to and expand vocab card
- [ ] Video–subtitle sync (seek embedded video on timestamp click)
- [ ] Pronunciation link (Forvo)
- [ ] Transcript search
- [ ] Recurring vocabulary ranking
- [ ] Spaced repetition (optional)

### Phase 6: Public Platform & Polish (Future)
- [ ] PostgreSQL migration
- [ ] Multi-user, auth
- [ ] Deployment (Render, Railway, etc.)
- [ ] Export to Anki
- [ ] Dark mode
- [ ] Mobile layout

---

## 📍 Current Status (Mar 14)

**What Works:**
- ✅ Transcript fetching (YouTube Transcript API)
- ✅ Playlist metadata (YouTube Data API)
- ✅ Database storage (SQLite, migrations)
- ✅ Vocabulary extraction (spaCy nl_core_news_md)
- ✅ Dictionary lookup (Wiktionary nl, gloss_en, fallback)
- ✅ Streamlit app: episode viewer, embedded video
- ✅ Clickable transcript with definition bubbles (no page reload)
- ✅ English meanings in bubbles (gloss_en, comparative forms)
- ✅ Segment translation (OpenAI, optional)
- ✅ Show/hide English translation toggle (default: hide)
- ✅ Related reading with date-filtered NOS links (±2 days)
- ✅ Topic extraction (OpenAI, optional)
- ✅ Exclude "Journaal" from vocabulary

**Scripts:**
- `ingest_playlist.py` — Ingest episodes
- `extract_vocabulary.py` — NLP vocabulary extraction
- `translate_segments.py` — LLM translation (optional)
- `extract_topics.py` — Topic extraction for Related reading
- `download_dictionary.py` — Wiktionary nl → Dutch/English

**Optional Next Steps:**
- ⏳ Run `extract_topics.py --all` for all episodes
- ⏳ Phase 4: Daily quiz system

---

## 💡 Quick Commands Reference

```bash
# Data pipeline
python scripts/ingest_playlist.py --init-db --max-videos 5
python scripts/extract_vocabulary.py --max 5

# Dictionary (one-time)
python scripts/download_dictionary.py

# Optional LLM enrichment (requires OPENAI_API_KEY)
python scripts/translate_segments.py --max 5
python scripts/extract_topics.py --max 5

# App
streamlit run app/main.py
```

---

## 🆘 If Lost Tomorrow Morning

1. Read this file first
2. Check `git status` and `git log --oneline -5`
3. Continue from first unchecked [ ] in "Tomorrow's Plan" or "This Week's Plan"

---

## 📝 Session Notes

### Mar 14, 2026
**Completed:**
- Translation toggle default → hide English
- Related reading: topics extraction, NOS links, date range (±2 days)
- README, ARCHITECTURE, TODO.md updated

**Key decisions:**
- NOS search doesn't expose date params → use Google `site:nos.nl` with `tbs=cdr:1`
- ±2 days around episode date for relevance
- Topics stored pipe-separated in Episode.topics

_(Add notes at end of each session)_
