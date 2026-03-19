# GitHub Actions — Daily Pipeline Setup

Steps to set up automated daily pipeline runs via GitHub Actions.

---

## Prerequisites (Done)

- [x] Neon Postgres database (`DATABASE_URL`)
- [x] Repository secrets: `DATABASE_URL`, `OPENAI_API_KEY` (and `YOUTUBE_API_KEY` if used)
- [x] Workflow permissions: Read repository contents (recommended)

---

## Step 1: Create the Workflow File

Create `.github/workflows/daily_pipeline.yml`:

```yaml
name: Daily Pipeline

on:
  schedule:
    # Weekdays: every 15 min from 18:00–20:00 UTC (NOS uploads ~18:00)
    - cron: '*/15 18-20 * * 1-5'
    # Weekends: once at 18:15 UTC
    - cron: '15 18 * * 0,6'
  workflow_dispatch:  # Allow manual trigger

jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          python -m spacy download nl_core_news_md

      - name: Run pipeline
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
        run: bash scripts/run_pipeline.sh
```

---

## Smart Scheduling (Episode Check)

The workflow runs every 10 min from 15:00–20:00 UTC (6pm–8pm Amsterdam). Whenever triggered (push, schedule, or manual), it checks:

- **Playlist vs DB:** Fetches the latest 100 videos from the YouTube playlist and compares against episodes in the DB (with `transcript_fetched`).
- If any playlist video is missing or not fully ingested → run pipeline.
- If all are present → skip pipeline.

No time window or date filter — the check runs whenever the workflow runs. Manual trigger supports a "Force run" option to bypass the check.

---

## Step 2: Verify Secrets

In **Settings → Secrets and variables → Actions**:

| Secret | Required | Used by |
|--------|----------|---------|
| `DATABASE_URL` | Yes | All steps (Neon Postgres) |
| `OPENAI_API_KEY` | Yes | enrich_vocab_llm, translate_segments, extract_topics |
| `YOUTUBE_API_KEY` | Yes | check_episode_needed, ingest_playlist (playlist fetch) |

---

## Step 3: Geo-Restriction Note

`youtube-transcript-api` can be geo-restricted. GitHub runners are typically in the US. If transcript fetch fails:

- **Option A:** Use a proxy/VPN in the workflow (e.g., `nordvpn` action)
- **Option B:** Run pipeline locally or on a server in NL
- **Option C:** Accept that some episodes may need manual transcript fetch

---

## Step 4: Test

1. Push the workflow file to a branch
2. Go to **Actions** tab → **Daily Pipeline**
3. Click **Run workflow** (manual trigger)
4. Check the run; verify new episode appears in Streamlit app

---

## Step 5: Update README/TODO

- Remove or de-emphasize cron instructions
- Add note: "Pipeline runs automatically via GitHub Actions"

---

## Optional: Retry on Failure

To retry failed steps (e.g., transient network issues):

```yaml
      - name: Run pipeline
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
        run: |
          for i in 1 2 3; do
            bash scripts/run_pipeline.sh && exit 0
            echo "Pipeline failed, retrying in 60s..."
            sleep 60
          done
          exit 1
```

---

## Optional: Cache spaCy Model

Speed up runs by caching the spaCy model:

```yaml
      - name: Cache spaCy model
        uses: actions/cache@v4
        with:
          path: ~/.local/lib/python3.11/site-packages/nl_core_news_md
          key: spacy-nl-core-news-md

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          python -m spacy download nl_core_news_md
```

---

## Summary Checklist

- [x] Create `.github/workflows/daily_pipeline.yml`
- [x] Update README/TODO
- [ ] Verify `DATABASE_URL`, `OPENAI_API_KEY`, `YOUTUBE_API_KEY` in repo secrets
- [ ] Push and trigger `workflow_dispatch` to test
- [ ] Confirm new episode in app
