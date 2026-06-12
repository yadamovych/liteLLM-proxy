#!/usr/bin/env bash
set -euo pipefail

wait_for_postgres() {
  local host="${POSTGRES_HOST:-postgres}"
  local user="${POSTGRES_USER:-litellm}"
  local db="${POSTGRES_DB:-litellm}"

  echo "Waiting for Postgres at ${host}:5432 ..."
  for attempt in $(seq 1 30); do
    if pg_isready -h "${host}" -U "${user}" -d "${db}" -q 2>/dev/null; then
      echo "Postgres is ready."
      return 0
    fi
    if (( attempt % 10 == 0 )); then
      echo "  still waiting (${attempt}/30) ..."
    fi
    sleep 1
  done

  echo "Timed out waiting for Postgres." >&2
  echo "  host lookup: $(getent hosts "${host}" 2>&1 || echo 'failed')" >&2
  echo "  tip: run 'docker compose ps' — postgres should be healthy" >&2
  echo "  tip: restart stack with './scripts/stop.sh && ./scripts/start.sh'" >&2
  exit 1
}

prisma_dir() {
  python3 - <<'PY'
import os
from litellm.proxy.db import prisma_client as pc
print(os.path.dirname(os.path.dirname(pc.__file__)))
PY
}

apply_schema() {
  if [[ -z "${DATABASE_URL:-}" ]]; then
    return 0
  fi
  local dir
  dir="$(prisma_dir)"
  echo "Applying database schema ..."
  (
    cd "${dir}"
    python3 -m prisma db push --accept-data-loss --skip-generate
  )
}

if [[ -n "${DATABASE_URL:-}" ]]; then
  wait_for_postgres
  apply_schema
fi

exec litellm "$@"
