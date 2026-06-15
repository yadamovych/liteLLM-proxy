#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
docker compose down
echo "Stopped. Data kept in Docker volumes (litellm_pg_data, litellm_cache)."
