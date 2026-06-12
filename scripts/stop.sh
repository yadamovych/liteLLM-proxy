#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"
docker compose down
echo "Stopped. Data kept in Docker volumes (litellm_pg_data, litellm_cache)."
