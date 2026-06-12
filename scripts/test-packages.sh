#!/usr/bin/env bash
# Local package tests (no Docker required). Run from repo root:
#   ./scripts/test-packages.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  echo "Missing .venv — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

echo "=== Package import tests ==="
"${PYTHON}" - <<'PY'
import bedrock_auto_router
import debug_summary_callback
from debug_summary_callback import proxy_handler_instance
from debug_summary_callback.builder import display_model_name
from debug_summary_callback.utils import is_copilot_payload, extract_usage_from_object
from bedrock_auto_router.vscode import extract_routing_intent, has_vscode_code_context, strip_vscode_wrapper
from bedrock_auto_router.intent import resolve_intent, needs_capable_model, is_short_greeting

assert hasattr(bedrock_auto_router, "BedrockAutoRouter")
assert proxy_handler_instance is not None
print("OK: imports and proxy_handler_instance")

# VS Code intent parsing
raw = "<context><userQuery>refactor this function</userQuery></context>"
assert extract_routing_intent(raw) == "refactor this function"
assert is_copilot_payload(raw)
assert not is_short_greeting("refactor this function")
assert needs_capable_model("refactor this function", raw)
print("OK: vscode intent parsing + coding detection")

plain = "<userQuery>hi</userQuery>"
assert is_short_greeting(resolve_intent(plain))
assert not needs_capable_model("hi", plain)
print("OK: plain short greeting stays simple")

# Code selection forces capable model
code_ctx = '<userQuery>help</userQuery><codeSelection>def foo(): pass</codeSelection>'
assert has_vscode_code_context(code_ctx)
print("OK: code selection detection")

# Callback utilities
usage = extract_usage_from_object({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
assert usage["prompt_tokens"] == 10
assert usage["completion_tokens"] == 5
name = display_model_name(
    {"model": "bedrock-auto"},
    {"model_group": "bedrock-auto", "model": "claude-haiku"},
    {},
)
assert name == "bedrock-auto"
print("OK: callback model display name")

# Router patch applied
from litellm.router import Router
assert getattr(Router.init_complexity_router_deployment, "_bedrock_auto_patched", False)
print("OK: bedrock_auto_router patch registered")
PY

echo ""
echo "All package tests passed."
