#!/usr/bin/env bash
# Create a LiteLLM virtual key (proxy must be running in Docker).
# Usage: ./create-key.sh [user-label] [max_budget_usd]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi

BASE_URL="${LITELLM_BASE_URL:-http://localhost:4000}"
MASTER_KEY="${LITELLM_MASTER_KEY:-sk-local-litellm-bedrock}"
USER_LABEL="${1:-dev}"
MAX_BUDGET="${2:-30}"

payload=$(printf '{"models":["bedrock-auto","claude-haiku","claude-sonnet","qwen3-coder"],"max_budget":%s,"budget_duration":"30d","metadata":{"user":"%s"},"key_alias":"%s"}' \
  "${MAX_BUDGET}" "${USER_LABEL}" "${USER_LABEL}")

response=$(curl -fsS -X POST "${BASE_URL}/key/generate" \
  -H "Authorization: Bearer ${MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d "${payload}")

if command -v python3 >/dev/null 2>&1; then
  python3 -c '
import json, sys
data = json.load(sys.stdin)
key = data.get("key") or data.get("token") or (data.get("info") or {}).get("token")
if not key:
    raise SystemExit(f"Unexpected response: {data}")
print(key)
' <<<"${response}"
else
  echo "${response}"
fi
