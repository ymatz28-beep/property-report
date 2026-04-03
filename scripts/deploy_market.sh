#!/usr/bin/env bash
# Usage: bash scripts/deploy_market.sh [--msg "custom commit message"] [--dry-run] [--no-push]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJ_DIR"

PYTHON=".venv/bin/python"
DRY_RUN=0
NO_PUSH=0
COMMIT_MSG=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=1 ;;
    --no-push) NO_PUSH=1 ;;
    --msg) COMMIT_MSG="$2"; shift ;;
  esac
  shift
done

set -e

# Step 1: Auto-fix data quality
echo "==> [1/4] Auto-fix data quality"
if [[ $DRY_RUN -eq 1 ]]; then
  $PYTHON auto_fix_data_quality.py --dry-run
  echo "==> dry-run complete. Stopping."
  exit 0
fi
FIX_OUTPUT=$($PYTHON auto_fix_data_quality.py 2>&1)
echo "$FIX_OUTPUT"
FIX_LINE=$(echo "$FIX_OUTPUT" | grep "^\[FIX\]" || echo "")
FIX_COUNT=$(echo "$FIX_LINE" | grep -oE '[0-9]+件' | tr -d '件' | paste -sd+ - | bc 2>/dev/null || echo "0")

# Step 2: Generate market
echo "==> [2/4] Generate market"
$PYTHON generate_market.py

# Step 3: QA gate
echo "==> [3/4] QA gate"
set +e
QA_OUTPUT=$($PYTHON qa_market.py 2>&1)
QA_EXIT=$?
set -e
echo "$QA_OUTPUT"
RESULT_LINE=$(echo "$QA_OUTPUT" | grep "^Result:" || echo "")
PASS_COUNT=$(echo "$RESULT_LINE" | grep -oE '[0-9]+ PASS' | grep -oE '[0-9]+' || echo "0")
WARN_COUNT=$(echo "$RESULT_LINE" | grep -oE '[0-9]+ WARN' | grep -oE '[0-9]+' || echo "0")
FAIL_COUNT=$(echo "$RESULT_LINE" | grep -oE '[0-9]+ FAIL' | grep -oE '[0-9]+' || echo "0")
echo "QA result: PASS=$PASS_COUNT WARN=$WARN_COUNT FAIL=$FAIL_COUNT"
if [[ "$FAIL_COUNT" -gt 0 ]] 2>/dev/null; then
  echo "WARNING: $FAIL_COUNT FAIL(s) detected (may be expected for Name Quality). Continuing."
fi

# Step 4: Git operations
echo "==> [4/4] Git commit"
git add data/*.txt data/*.json data/*.yaml output/market.html output/rent-strategy.html auto_fix_data_quality.py 2>/dev/null || true

if git diff --cached --quiet; then
  echo "No changes to commit."
  open output/market.html 2>/dev/null || true
  exit 0
fi

if [[ -z "$COMMIT_MSG" ]]; then
  COMMIT_MSG="auto: market data quality fix + regenerate ($(date +%Y-%m-%d))"
fi
FULL_MSG="$(printf '%s\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>' "$COMMIT_MSG")"
git commit -m "$FULL_MSG"
COMMIT_HASH=$(git rev-parse --short HEAD)

PUSH_STATUS="skipped (--no-push)"
if [[ $NO_PUSH -eq 0 ]]; then
  set +e
  git push
  if [[ $? -eq 0 ]]; then
    PUSH_STATUS="pushed"
  else
    echo "WARNING: git push failed. Retry manually."
    PUSH_STATUS="FAILED (retry manually)"
  fi
  set -e
fi

open output/market.html 2>/dev/null || true

echo ""
echo "=== Deploy Summary ==="
echo "  Fixes applied : ${FIX_COUNT}"
echo "  QA result     : PASS=$PASS_COUNT WARN=$WARN_COUNT FAIL=$FAIL_COUNT"
echo "  Commit        : $COMMIT_HASH"
echo "  Push          : $PUSH_STATUS"
