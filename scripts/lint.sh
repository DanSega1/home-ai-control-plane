#!/usr/bin/env bash
# scripts/lint.sh  –  run all linters for home-ai-control-plane
# Usage:
#   ./scripts/lint.sh           # check only
#   ./scripts/lint.sh --fix     # auto-fix where possible

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FIX=""
if [[ "${1:-}" == "--fix" ]]; then
  FIX="--fix"
  echo "Running ruff in FIX mode…"
else
  echo "Running ruff in CHECK mode (pass --fix to auto-fix)…"
fi

# ── Python: ruff lint ──────────────────────────────────────────────────────────
echo ""
echo "▶ ruff check"
ruff check $FIX \
  services/ \
  agents/ \
  contracts/ \
  scripts/

# ── Python: ruff format ────────────────────────────────────────────────────────
echo ""
echo "▶ ruff format"
if [[ -n "$FIX" ]]; then
  ruff format services/ agents/ contracts/ scripts/
else
  ruff format --check services/ agents/ contracts/ scripts/
fi

# ── OPA: policy syntax check ────────────────────────────────────────────────────
echo ""
echo "▶ opa check (policies/)"
if command -v opa &>/dev/null; then
  opa check policies/
elif docker ps --format '{{.Names}}' | grep -q homeai-opa; then
  docker exec homeai-opa opa check /policies
else
  echo "  [skip] opa not found locally and homeai-opa container not running"
fi

echo ""
echo "✅  All checks passed."
