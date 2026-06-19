# LiteLLM → AWS Bedrock (Docker)

OpenAI-compatible proxy for VS Code `litellm-vscode-chat`. Everything runs in **Docker** (LiteLLM + Postgres) — no local Python venv.

## Prerequisites

- **Docker** in WSL
- **AWS CLI** on the host with configured profile (`~/.aws/config`)
- `curl` for verify/create-key scripts

## Quick start

```bash
cd ~/liteLLM-proxy
cp .env.example .env    # first time only

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
```

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
| `bedrock-auto` | VS Code-aware auto routing (recommended) |
| `claude-sonnet` / `claude-sonnet-4.6` | Claude Sonnet 4.6 |
| `claude-haiku` / `claude-haiku-4.5` | Claude Haiku 4.5 |
| `qwen3-coder` | Qwen3 Coder 30B (Bedrock) |
| `nova-lite` | Amazon Nova Lite (optional) |

### `bedrock-auto` routing

Strips VS Code XML context before scoring, then routes by chat mode first:

| Mode / case | Model |
|-------------|-------|
| Plan | Sonnet |
| Ask / Agent | Qwen3 Coder |
| Simple / coding (non-IDE) | Qwen3 Coder |
| Medium complexity | Haiku |
| Complex / reasoning | Sonnet |

## Features

- **Disk cache** — Docker volume `litellm_cache`
- **Cost footer** — appended to chat replies (`LITELLM_COST_FOOTER=1`)
- **Debug logs** — `./scripts/start.sh --debug` → `[litellm:debug] model=... tokens=...`

## Layout

```
liteLLM-proxy/
  Dockerfile
  docker-compose.yml
  litellm_config.yaml
  src/
    callbacks/              # debug logs + cost footer
    core/                   # bedrock-auto VS Code-aware router
  docker/entrypoint.sh
  scripts/                  # start, stop, logs, verify, create-key
```

## VS Code

1. `Ctrl+Shift+P` → **Manage LiteLLM Provider**
2. Base URL: `http://localhost:4000`
3. API Key: virtual key from `./scripts/create-key.sh`
4. Model: **`bedrock-auto`** (recommended)
5. **LiteLLM: Test Connection**
