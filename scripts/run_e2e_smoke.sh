#!/usr/bin/env bash
# Run Phase 1 smoke test against docker-compose stack.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="infra/docker-compose.yml"
BASE_URL="${BASE_URL:-http://localhost:8000}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-240}"
POLL_SECONDS="${POLL_SECONDS:-2}"

cleanup() {
  if [[ "${KEEP_STACK_UP:-0}" != "1" ]]; then
    docker compose -f "$COMPOSE_FILE" down >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

echo "[e2e-smoke] starting docker compose stack"
docker compose -f "$COMPOSE_FILE" up -d --build

echo "[e2e-smoke] waiting for supervisor health"
for i in {1..60}; do
  if curl -sf "$BASE_URL/health" >/dev/null; then
    break
  fi
  sleep 2
  if [[ "$i" == "60" ]]; then
    echo "[e2e-smoke] FAILED: supervisor did not become healthy in time" >&2
    exit 1
  fi
done

echo "[e2e-smoke] running smoke scenario"
python3 scripts/e2e_smoke.py \
  --base-url "$BASE_URL" \
  --timeout-seconds "$TIMEOUT_SECONDS" \
  --poll-interval-seconds "$POLL_SECONDS"

echo "[e2e-smoke] PASSED"
