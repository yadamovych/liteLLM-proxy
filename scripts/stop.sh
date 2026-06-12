#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker compose down
echo "Stopped. Data kept in Docker volumes (litellm_pg_data, litellm_cache)."
