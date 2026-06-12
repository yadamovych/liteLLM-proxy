# Kilo Project Preferences

- Do not delete any files or folders without explicit user approval.
- Treat `.kilo/plans/professional-restructure.md` as the source of truth for the professional folder restructure.
- For the debug summary callback refactor, the user requested the full multi-file refactoring, no unit tests, Python 3.12+ typing, and a shared `src/core/_vscode_context.py` module.
- The debug summary callback is now located at `src/callbacks/` with `proxy_handler_instance` exported from `src/callbacks/__init__.py`.
- The bedrock auto router is now located at `src/core/router.py` with `BedrockAutoRouter` exported from `src/core/__init__.py`.
- If future work touches the debug summary callback refactor, preserve the multi-file package structure and existing public API (`proxy_handler_instance`).
