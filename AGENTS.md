# Kilo Project Preferences

- Do not delete any files or folders without explicit user approval.
- Operational scripts live in `scripts/` (e.g. `./scripts/start.sh`).
- Python packages: `bedrock_auto_router/` (includes VS Code prompt parsing), `debug_summary_callback/`.
- For the debug summary callback refactor: full multi-file package structure, no unit tests, Python 3.12+ typing.
- Preserve the public LiteLLM callback API: `custom_callbacks.proxy_handler_instance` (shim beside `litellm_config.yaml`; implementation in `debug_summary_callback/`).
