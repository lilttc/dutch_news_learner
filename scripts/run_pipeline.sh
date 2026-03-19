#!/usr/bin/env bash
#
# Daily pipeline for Dutch News Learner.
# Runs all enrichment steps in order. By default, each step only processes
# episodes that need it (incremental). Pass --all to re-process everything,
# or --max N to limit scope.
#
# Usage:
#   bash scripts/run_pipeline.sh            # Incremental (only new/missing data)
#   bash scripts/run_pipeline.sh --all      # Re-process all episodes
#   bash scripts/run_pipeline.sh --max 3    # Limit to 3 newest per step
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
log "Step 1/7: Ingesting new episodes..."
python scripts/ingest_playlist.py "${EXTRA_ARGS[@]}"

# Step 2: Extract vocabulary (spaCy NLP)
log "Step 2/7: Extracting vocabulary..."
python scripts/extract_vocabulary.py "${EXTRA_ARGS[@]}"

# Step 3: Enrich vocabulary with dictionary translations
log "Step 3/7: Enriching vocabulary (dictionary)..."
python scripts/enrich_vocabulary.py

# Step 4: Enrich vocabulary with LLM (fills gaps the dictionary missed)
if grep -q "OPENAI_API_KEY" .env 2>/dev/null; then
    log "Step 4/7: Enriching vocabulary (LLM)..."
    python scripts/enrich_vocab_llm.py --all
else
    log "Step 4/7: Skipping LLM enrichment (OPENAI_API_KEY not in .env)"
fi

# Step 5: Translate segments (OpenAI — skipped if no API key)
if grep -q "OPENAI_API_KEY" .env 2>/dev/null; then
    log "Step 5/7: Translating segments..."
    python scripts/translate_segments.py "${EXTRA_ARGS[@]}"
else
    log "Step 5/7: Skipping translation (OPENAI_API_KEY not in .env)"
fi

# Step 6: Extract topics (OpenAI — skipped if no API key)
if grep -q "OPENAI_API_KEY" .env 2>/dev/null; then
    log "Step 6/7: Extracting topics..."
    python scripts/extract_topics.py "${EXTRA_ARGS[@]}"
else
    log "Step 6/7: Skipping topic extraction (OPENAI_API_KEY not in .env)"
fi

# Step 7: Fetch related NOS articles (DuckDuckGo — no API key needed)
log "Step 7/7: Fetching related articles..."
python scripts/fetch_related_articles.py "${EXTRA_ARGS[@]}"

log "========== Pipeline complete =========="
