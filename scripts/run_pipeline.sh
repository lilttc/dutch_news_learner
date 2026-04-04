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
log "Step 1/8: Ingesting new episodes..."
python scripts/ingest_playlist.py "${EXTRA_ARGS[@]}"

# Step 2: Extract vocabulary (spaCy NLP)
log "Step 2/8: Extracting vocabulary..."
python scripts/extract_vocabulary.py "${EXTRA_ARGS[@]}"

# Step 3: Enrich vocabulary with dictionary translations
log "Step 3/8: Enriching vocabulary (dictionary)..."
python scripts/enrich_vocabulary.py

# Step 4: Enrich vocabulary with LLM (fills gaps the dictionary missed)
# Check env var (CI) or .env file (local)
if [ -n "${OPENAI_API_KEY:-}" ] || grep -q "OPENAI_API_KEY" .env 2>/dev/null; then
    log "Step 4/8: Enriching vocabulary (LLM)..."
    python scripts/enrich_vocab_llm.py --all
else
    log "Step 4/8: Skipping LLM enrichment (OPENAI_API_KEY not set)"
fi

# Step 5: Translate segments (OpenAI — skipped if no API key)
if [ -n "${OPENAI_API_KEY:-}" ] || grep -q "OPENAI_API_KEY" .env 2>/dev/null; then
    log "Step 5/8: Translating segments..."
    python scripts/translate_segments.py "${EXTRA_ARGS[@]}"
else
    log "Step 5/8: Skipping translation (OPENAI_API_KEY not set)"
fi

# Step 6: Extract topics (OpenAI — skipped if no API key)
if [ -n "${OPENAI_API_KEY:-}" ] || grep -q "OPENAI_API_KEY" .env 2>/dev/null; then
    log "Step 6/8: Extracting topics..."
    python scripts/extract_topics.py "${EXTRA_ARGS[@]}"
else
    log "Step 6/8: Skipping topic extraction (OPENAI_API_KEY not set)"
fi

# Step 7: Fetch related NOS articles (DuckDuckGo — no API key needed)
log "Step 7/8: Fetching related articles..."
python scripts/fetch_related_articles.py "${EXTRA_ARGS[@]}"

# Step 8: LLM-as-judge vocab QA (fixes POS errors, wrong translations, flags idioms)
if [ -n "${OPENAI_API_KEY:-}" ] || grep -q "OPENAI_API_KEY" .env 2>/dev/null; then
    log "Step 8/8: Running vocab QA agent..."
    python scripts/qa_vocab_llm.py "${EXTRA_ARGS[@]}"
else
    log "Step 8/8: Skipping vocab QA (OPENAI_API_KEY not set)"
fi

log "========== Pipeline complete =========="
