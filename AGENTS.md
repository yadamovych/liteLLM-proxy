# Kilo Project Preferences

- Do not delete any files or folders without explicit user approval.
- Treat `.kilo/plans/debug-summary-callback-refactor.md` as the source of truth for the debug summary callback refactor.
- For the debug summary callback refactor, the user requested the full multi-file refactoring, no unit tests, Python 3.12+ typing, and a shared `vscode_context.py` module.
- If future work touches the debug summary callback refactor, preserve the multi-file package structure and existing public API (`proxy_handler_instance`).
