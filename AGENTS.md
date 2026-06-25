# Kilo Project Preferences

- Do not delete any files or folders without explicit user approval.
- Treat `.kilo/plans/professional-restructure.md` as the source of truth for the professional folder restructure.
- For the debug summary callback refactor, the user requested the full multi-file refactoring, no unit tests, Python 3.12+ typing, and a shared `src/core/_vscode_context.py` module.
- The debug summary callback is now located at `src/callbacks/` with `proxy_handler_instance` exported from `src/callbacks/__init__.py`.
- The bedrock auto router is now located at `src/core/router.py` with `BedrockAutoRouter` exported from `src/core/__init__.py`.
- If future work touches the debug summary callback refactor, preserve the multi-file package structure and existing public API (`proxy_handler_instance`).

## Cursor Cloud specific instructions

This is a Docker-first product: an OpenAI-compatible LiteLLM proxy in front of AWS Bedrock, plus a Postgres DB and an Admin UI. There is no `requirements.txt`/`pyproject.toml`; the proxy's Python deps live in the `Dockerfile`. See `README.md` for the user-facing commands (`scripts/start.sh`, `scripts/stop.sh`, `scripts/verify-proxy.sh`, `scripts/create-key.sh`).

### Running the app (proxy + Postgres)
- The Docker daemon does NOT auto-start (PID 1 is `tini`, no systemd). Start it once per session before any docker command: `sudo dockerd` (run it backgrounded, e.g. in a tmux session). The `ubuntu` user is in the `docker` group, so `docker`/`docker compose` work without sudo once the daemon is up.
- Bring the stack up from the repo root with `docker compose up -d --build` (or `./scripts/start.sh`, which also tails logs). Proxy: http://localhost:4000, Admin UI: http://localhost:4000/ui.
- `.env` is gitignored and required; `scripts/start.sh` auto-creates it from `.env.example`. The dev `.env` here uses `LITELLM_MASTER_KEY=sk-local-dev-master-key-12345` and UI creds `admin` / `admin-dev-password`.
- GOTCHA: On a FRESH Postgres volume the first proxy startup runs a LiteLLM baseline migration that resolves ~124 migrations sequentially (~4s each), so it can take ~10 minutes before `/health/liveliness` returns 200 and the container reports healthy. This is one-time; the `litellm_pg_data` volume persists, so later starts are fast. Do not assume the build hung — watch `docker compose logs -f litellm`.
- The compose file bind-mounts `~/.aws` read-only into the container. This VM has no real AWS credentials, so actual Bedrock chat completions fail at credential resolution (`The config profile could not be found`). Everything else — proxy startup, DB, Admin UI, `/v1/model/info`, `/v1/models`, virtual-key management, and the `bedrock-auto` pre-routing classification — works without AWS. Full end-to-end chat needs a real AWS profile in `~/.aws` (and `aws sso login`).

### Tests / lint
- Unit tests import `litellm` and the `src/` packages, so they run in a local venv (the Docker image has no pytest). A `.venv` (gitignored) is created by the update script with `litellm[proxy,caching,extra-proxy]==1.88.1` + pytest matching the Dockerfile. Run with: `source .venv/bin/activate && python -m pytest`.
- `tests/test_integration.py` is only a placeholder; live integration testing is done via `./scripts/verify-proxy.sh` against a running proxy (requires AWS for the chat smoke tests).
- No linter/formatter is configured in this repo (no ruff/flake8/mypy/black config). `python -m py_compile` is the only available syntax check.
