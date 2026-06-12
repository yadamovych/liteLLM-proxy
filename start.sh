#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

DEBUG=0
if [[ "${1:-}" == "--debug" || "${1:-}" == "-d" ]]; then
  DEBUG=1
fi

if [[ ! -f .env ]] && [[ -f .env.example ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if [[ "${DEBUG}" == "1" ]]; then
  export LITELLM_LOG=INFO
  export LITELLM_DEBUG=1
  echo "Debug logging enabled."
else
  export LITELLM_LOG=WARNING
  unset LITELLM_DEBUG || true
fi

echo "Building and starting LiteLLM + Postgres (Docker) ..."
docker compose up -d --build

echo ""
echo "Proxy:  http://localhost:4000"
echo "UI:     http://localhost:4000/ui"
echo "Logs:   ./logs.sh"
echo "Verify: ./verify-proxy.sh"
echo ""
echo "AWS SSO (host): aws sso login --profile aws.it.saas.test2-ia"
