#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi

BASE_URL="${LITELLM_BASE_URL:-http://localhost:4000}"
API_KEY="${LITELLM_MASTER_KEY:-sk-local-litellm-bedrock}"

echo "Checking LiteLLM proxy (Docker) at ${BASE_URL} ..."

MODEL_INFO=$(curl -fsS -H "Authorization: Bearer ${API_KEY}" "${BASE_URL}/v1/model/info")
MODEL_COUNT=$(python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("data", [])))' <<<"$MODEL_INFO")
echo "OK: /v1/model/info returned ${MODEL_COUNT} models"
python3 -c 'import json,sys; [print("  - "+str(m.get("model_name", m.get("id","?")))) for m in json.load(sys.stdin).get("data",[])]' <<<"$MODEL_INFO"

DUPE_CHECK=$(python3 -c '
import json, sys
from collections import Counter
names = [m.get("model_name") for m in json.load(sys.stdin).get("data", []) if m.get("model_name")]
dupes = [n for n, c in Counter(names).items() if c > 1]
print(",".join(dupes))
' <<<"$MODEL_INFO")
if [[ -n "${DUPE_CHECK}" ]]; then
  echo "WARN: duplicate model_name in /v1/model/info: ${DUPE_CHECK}" >&2
fi

CACHE_MODELS=$(python3 -c '
import json, sys
data = json.load(sys.stdin).get("data", [])
names = []
for m in data:
    info = m.get("model_info") or {}
    if info.get("supports_prompt_caching"):
        names.append(m.get("model_name", "?"))
print(",".join(sorted(set(names))))
' <<<"$MODEL_INFO")
if [[ -n "${CACHE_MODELS}" ]]; then
  echo "OK: prompt caching advertised for: ${CACHE_MODELS}"
else
  echo "WARN: no models report supports_prompt_caching" >&2
fi

_test_chat() {
  local model="$1"
  local chat
  chat=$(curl -fsS -H "Authorization: Bearer ${API_KEY}" -H "Content-Type: application/json" \
    -d "{\"model\":\"${model}\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":32}" \
    "${BASE_URL}/v1/chat/completions")
  local reply
  reply=$(python3 -c 'import json,sys; r=json.load(sys.stdin); print(r["choices"][0]["message"].get("content") or "")' <<<"$chat")
  if [[ -z "${reply}" ]]; then
    echo "FAIL: ${model} returned empty content" >&2
    python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin), indent=2)[:800])' <<<"$chat" >&2
    return 1
  fi
  echo "OK: ${model} -> ${reply}"
}

_test_chat claude-haiku
_test_chat qwen3-coder

if curl -fsS -o /dev/null -w "" "${BASE_URL}/ui" 2>/dev/null; then
  echo "OK: Admin UI reachable at ${BASE_URL}/ui"
else
  echo "WARN: Admin UI not reachable (is ./start.sh running?)" >&2
fi

cat <<EOF

Proxy is ready.

VS Code (litellm-vscode-chat):
  Base URL: ${BASE_URL}
  API Key:  <virtual key from UI or ./create-key.sh dev>
  Admin UI: ${BASE_URL}/ui  (master key for key management only)

Create a dev key:  ./create-key.sh alice 30
Command Palette -> 'Manage LiteLLM Provider' or 'LiteLLM: Test Connection'
EOF
