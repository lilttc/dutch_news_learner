#!/usr/bin/env bash
#
# Daily pipeline for Dutch News Learner.
# Runs all enrichment steps in order — each script skips already-processed episodes.
#
# Usage:
#   bash scripts/run_pipeline.sh            # Full pipeline
#   bash scripts/run_pipeline.sh --max 3    # Limit to 3 newest episodes per step
#
# Cron example (run daily at 20:00):
#   0 20 * * * cd /path/to/dutch_news_learner && bash scripts/run_pipeline.sh >> logs/pipeline.log 2>&1

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Forward all arguments (e.g. --max 3) to each script
EXTRA_ARGS=("$@")

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "========== Dutch News Learner — Daily Pipeline =========="

# Step 1: Ingest new episodes from YouTube playlist
log "Step 1/5: Ingesting new episodes..."
python scripts/ingest_playlist.py "${EXTRA_ARGS[@]}"

# Step 2: Extract vocabulary (spaCy NLP)
log "Step 2/5: Extracting vocabulary..."
python scripts/extract_vocabulary.py "${EXTRA_ARGS[@]}"

# Step 3: Translate segments (OpenAI — skipped if no API key)
if grep -q "OPENAI_API_KEY" .env 2>/dev/null; then
    log "Step 3/5: Translating segments..."
    python scripts/translate_segments.py "${EXTRA_ARGS[@]}"
else
    log "Step 3/5: Skipping translation (OPENAI_API_KEY not in .env)"
fi

# Step 4: Extract topics (OpenAI — skipped if no API key)
if grep -q "OPENAI_API_KEY" .env 2>/dev/null; then
    log "Step 4/5: Extracting topics..."
    python scripts/extract_topics.py "${EXTRA_ARGS[@]}"
else
    log "Step 4/5: Skipping topic extraction (OPENAI_API_KEY not in .env)"
fi

# Step 5: Fetch related NOS articles (DuckDuckGo — no API key needed)
log "Step 5/5: Fetching related articles..."
python scripts/fetch_related_articles.py "${EXTRA_ARGS[@]}"

log "========== Pipeline complete =========="
