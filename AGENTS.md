# Kilo Project Preferences

- Do not delete any files or folders without explicit user approval.
- Operational scripts live in `scripts/` (e.g. `./scripts/start.sh`).
- Python packages: `bedrock_auto_router/`, `debug_summary_callback/`, shared `vscode_context.py`.
- For the debug summary callback refactor: full multi-file package structure, no unit tests, Python 3.12+ typing, shared `vscode_context.py` module.
- Preserve the public LiteLLM callback API: `debug_summary_callback.proxy_handler_instance`.
