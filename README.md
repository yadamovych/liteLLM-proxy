# LiteLLM → AWS Bedrock (Docker)

OpenAI-compatible proxy for VS Code `litellm-vscode-chat`. Everything runs in **Docker** (LiteLLM + Postgres) — no local Python venv.

## Prerequisites

- **Docker** in WSL
- **AWS CLI** on the host with configured profile (`~/.aws/config`)
- `curl` for verify/create-key scripts

## Quick start

```bash
cd ~/litellm-bedrock
cp .env.example .env    # first time only

aws sso login --profile YOUR_AWS_PROFILE

chmod +x start.sh stop.sh logs.sh verify-proxy.sh create-key.sh
./start.sh              # build + start
./start.sh --debug      # verbose per-request logs
```

| URL | Purpose |
|-----|---------|
| http://localhost:4000 | OpenAI-compatible API |
| http://localhost:4000/ui | Admin UI (virtual keys) |

**VS Code:** use a **virtual key** from `./create-key.sh alice 30` or the UI — not the master key.

## Commands

```bash
./start.sh [--debug]   # up -d --build
./stop.sh              # down (keeps volumes)
./logs.sh              # follow proxy logs
./verify-proxy.sh      # health + chat test
./create-key.sh dev 30 # new virtual key
```

## AWS credentials

The container mounts **`~/.aws`** read-only. Refresh SSO on the host when tokens expire:

```bash
aws sso login --profile YOUR_AWS_PROFILE
docker compose restart litellm
```

If Docker cannot resolve `$HOME`, set in `.env`:

```
AWS_CONFIG_DIR=YOUR_AWS_CONFIG_DIR_PATH
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
- **Debug logs** — `./start.sh --debug` → `[litellm:debug] model=... tokens=...`

## Layout

```
litellm-bedrock/
  Dockerfile
  docker-compose.yml
  docker/entrypoint.sh      # wait for Postgres, prisma db push, start proxy
  litellm_config.yaml
  bedrock_auto_router.py    # VS Code-aware bedrock-auto routing
  debug_summary_callback.py # debug logs + cost footer
  start.sh stop.sh logs.sh
  create-key.sh verify-proxy.sh
```

## VS Code

1. `Ctrl+Shift+P` → **Manage LiteLLM Provider**
2. Base URL: `http://localhost:4000`
3. API Key: virtual key from `./create-key.sh`
4. **LiteLLM: Test Connection**
