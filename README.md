# LiteLLM → AWS Bedrock (Docker)

OpenAI-compatible proxy for VS Code `litellm-vscode-chat`. Everything runs in **Docker** (LiteLLM + Postgres) — no local Python venv.

## Prerequisites

- **Docker** in WSL
- **AWS CLI** on the host with configured profile (`~/.aws/config`)
- `curl` for verify/create-key scripts

## Quick start

```bash
cd ~/litellm-bedrock
cp .env.example .env    # first time only — set LITELLM_MASTER_KEY and UI_PASSWORD

aws sso login --profile YOUR_AWS_PROFILE

chmod +x scripts/*.sh
./scripts/start.sh              # build + start
./scripts/start.sh --debug      # verbose per-request logs
```

| URL | Purpose |
|-----|---------|
| http://localhost:4000 | OpenAI-compatible API |
| http://localhost:4000/ui | Admin UI (virtual keys) |

**VS Code:** use a **virtual key** from `./scripts/create-key.sh alice 30` or the UI — not the master key.

## Commands

```bash
./scripts/start.sh [--debug]   # up -d --build
./scripts/stop.sh              # down (keeps volumes)
./scripts/logs.sh              # follow proxy logs
./scripts/verify-proxy.sh      # health + chat test
./scripts/create-key.sh dev 30 # new virtual key
./scripts/key-info.sh sk-...   # key budget/spend
```

## Secrets

- Copy `.env.example` → `.env` and set unique `LITELLM_MASTER_KEY` and `UI_PASSWORD` before first run.
- Never commit `.env` or virtual keys printed by `create-key.sh`.
- AWS credentials stay on the host (`~/.aws` mount); the container does not store AWS keys in the repo.
- `POSTGRES_PASSWORD` in `.env` is a **local-dev-only** default for the Docker Postgres service.

## AWS credentials

The container mounts **`~/.aws`** read-only. Refresh SSO on the host when tokens expire:

```bash
aws sso login --profile YOUR_AWS_PROFILE
docker compose restart litellm
```

## Virtual keys

Login to http://localhost:4000/ui with `UI_USERNAME` / `UI_PASSWORD` from `.env`.

Master key (`LITELLM_MASTER_KEY`) is for admin/API only.

## Models

| Name | Backend |
|------|---------|
| `claude-sonnet` | Claude Sonnet 4.6 |
| `claude-haiku` | Claude Haiku 4.5 |
| `bedrock-auto` | Auto Haiku/Sonnet routing (VS Code-aware) |
| `nova-lite`, `qwen3-32b`, `qwen3-coder` | Optional Bedrock models |

`bedrock-auto` strips VS Code XML context before scoring; coding tasks route to Sonnet.

## Features

- **Disk cache** — Docker volume `litellm_cache`
- **Cost footer** — appended to chat replies (`LITELLM_COST_FOOTER=1`)
- **Debug logs** — `./scripts/start.sh --debug` → `[litellm:debug] model=... tokens=...`

## Layout

```
litellm-bedrock/
  Dockerfile
  docker-compose.yml
  docker/entrypoint.sh           # wait for Postgres, prisma db push, start proxy
  litellm_config.yaml
  vscode_context.py              # shared VS Code/Copilot text parsing
  bedrock_auto_router/           # VS Code-aware bedrock-auto routing
  debug_summary_callback/        # debug logs + cost footer callback
  scripts/
    start.sh stop.sh logs.sh
    verify-proxy.sh create-key.sh key-info.sh
  pyproject.toml
  requirements.txt
```

## VS Code

1. `Ctrl+Shift+P` → **Manage LiteLLM Provider**
2. Base URL: `http://localhost:4000`
3. API Key: virtual key from `./scripts/create-key.sh`
4. **LiteLLM: Test Connection**
