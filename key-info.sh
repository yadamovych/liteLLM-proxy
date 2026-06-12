#!/usr/bin/env bash
# Show budget and spend for a virtual key.
# Usage: ./key-info.sh sk-...
set -euo pipefail

KEY="${1:-}"
if [[ -z "${KEY}" ]]; then
  echo "Usage: $0 <virtual-key>" >&2
  exit 1
fi

if [[ -f .env ]]; then source .env; fi
BASE_URL="${LITELLM_BASE_URL:-http://localhost:4000}"

curl -fsS "${BASE_URL}/key/info" \
  -H "Authorization: Bearer ${KEY}" \
| python3 -c '
import json, sys
d = json.load(sys.stdin)
info = d.get("info", d)
spend    = info.get("spend", 0)
budget   = info.get("max_budget")
dur      = info.get("budget_duration", "?")
reset_at = info.get("budget_reset_at", "?")
models   = info.get("models", [])
alias    = info.get("key_alias", "?")
rpm      = info.get("rpm_limit", "unlimited")
tpm      = info.get("tpm_limit", "unlimited")

print(f"Key alias : {alias}")
print(f"Spend     : ${spend:.4f}" + (f" / ${budget:.2f}  ({dur})" if budget else "  (no budget limit)"))
print(f"Remaining : " + (f"${(budget - spend):.4f}" if budget else "unlimited"))
print(f"Reset at  : {reset_at}")
print(f"RPM limit : {rpm}")
print(f"TPM limit : {tpm}")
print(f"Models    : {', '.join(models) if models else 'all'}")
'
