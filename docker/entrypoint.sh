#!/usr/bin/env bash
set -euo pipefail

wait_for_postgres() {
  echo "Waiting for Postgres ..."
  for _ in $(seq 1 60); do
    if python - <<'PY'
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(("postgres", 5432))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
    then
      echo "Postgres is ready."
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for Postgres." >&2
  exit 1
}

prisma_dir() {
  python - <<'PY'
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
    python -m prisma db push --accept-data-loss --skip-generate
  )
}

if [[ -n "${DATABASE_URL:-}" ]]; then
  wait_for_postgres
  apply_schema
fi

exec litellm "$@"
