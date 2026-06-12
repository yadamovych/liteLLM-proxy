# Professional Folder Structure Reorganization Plan

## Current State Analysis

### Issues with Current Structure
1. **Flat top-level files**: `debug_summary_callback.py` (664 lines) and `bedrock_auto_router.py` (254 lines) should be packages
2. **Inconsistent modularization**: `debug_summary_callback/` is a package with 8 files, but `bedrock_auto_router.py` remains monolithic
3. **Duplicated code**: `vscode_context.py` exists separately; similar logic exists in both `bedrock_auto_router.py` and `debug_summary_callback/utils.py`
4. **No clear separation**: Root contains shell scripts, config, and Python code without logical grouping
5. **Missing standard structure**: No `tests/`, `scripts/`, or documented module boundaries

## Proposed Structure

```
litellm-bedrock/
├── .kilo/                          # Kilo configuration (no change)
├── .litellm_cache/                 # LiteLLM cache (no change)
├── .venv/                          # Virtual environment (no change)
├── .vscode/                        # VS Code config (no change)
├── src/                            # NEW: Main source code
│   ├── __init__.py                 # Package init
│   ├── core/                       # NEW: Core routing logic
│   │   ├── __init__.py
│   │   ├── router.py               # bedrock_auto_router.py
│   │   ├── __pycache__/
│   │   └── _vscode_context.py     # Shared VS Code detection
│   ├── callbacks/                  # NEW: Debug callback system
│   │   ├── __init__.py
│   │   ├── handler.py              # DebugSummaryHandler
│   │   ├── builder.py              # DebugLogBuilder
│   │   ├── cost.py                 # Cost calculation
│   │   ├── routes.py               # Route metadata extraction
│   │   ├── streams.py              # Streaming logic
│   │   ├── types.py                # Type definitions
│   │   ├── utils.py                # Shared utilities
│   │   └── __pycache__/
│   └── config/                     # NEW: Configuration handling
│       ├── __init__.py
│       ├── loader.py               # Load .env, yaml, etc.
│       └── validators.py           # Validate configuration
├── scripts/                        # NEW: Replacement for root shell scripts
│   ├── start.sh
│   ├── stop.sh
│   ├── logs.sh
│   ├── verify-proxy.sh
│   ├── create-key.sh
│   └── key-info.sh
├── docker/                         # (no change)
├── tests/                          # NEW: Unit/integration tests
│   ├── __init__.py
│   ├── test_router.py
│   ├── test_callbacks.py
│   └── test_integration.py
├── docs/                           # NEW: Documentation
│   ├── api.md
│   ├── architecture.md
│   └── setup.md
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── litellm_config.yaml
├── start.sh                        # Symlink → ../scripts/start.sh
├── stop.sh                         # Symlink → ../scripts/stop.sh
├── logs.sh                         # Symlink → ../scripts/logs.sh
├── verify-proxy.sh                 # Symlink → ../scripts/verify-proxy.sh
├── create-key.sh                   # Symlink → ../scripts/create-key.sh
├── key-info.sh                     # Symlink → ../scripts/key-info.sh
├── README.md
├── AGENTS.md
├── pyproject.toml                  # NEW: Python project metadata
└── requirements.txt                # NEW: Explicit dependencies
```

## Key Improvements

### 1. **Source Code Organization**
- **`src/`** as the single entry point for production code
- **Logical grouping**: `core/`, `callbacks/`, `config/`
- **Clear boundaries**: Each module has a single responsibility
- **Hidden internals**: `_vscode_context.py` (private module for shared logic)

### 2. **Code Deduplication**
- Merge `vscode_context.py` into `src/core/_vscode_context.py` (private)
- Update imports in both `src/core/router.py` and `src/callbacks/utils.py`
- Eliminate code duplication across files

### 3. **Standard Python Project Structure**
- **`src/` layout**: Industry best practice for Python projects
- **`tests/`**: Dedicated test directory
- **`scripts/`**: Move from root to avoid clutter
- **`docs/`**: Separate documentation from code

### 4. **Better Maintainability**
- Clear module boundaries make it easier to locate code
- Type hints and docstrings documented per module
- Smaller, focused files (max 300-400 lines each)
- Easier to test individual components

### 5. **Project Metadata**
- **`pyproject.toml`**: Modern Python project config (build system, dependencies)
- **`requirements.txt`**: Explicit runtime dependencies

## Migration Steps

### Phase 1: Create New Structure
1. Create `src/`, `src/core/`, `src/callbacks/`, `src/config/`, `scripts/`, `tests/`, `docs/`
2. Move `debug_summary_callback.py` → `src/callbacks/handler.py` + related files
3. Move `bedrock_auto_router.py` → `src/core/router.py`
4. Create `src/core/_vscode_context.py` and deduplicate code
5. Create `src/callbacks/__init__.py` with proper exports

### Phase 2: Update Imports
1. Update `litellm_config.yaml` to use `src.callbacks.handler.proxy_handler_instance`
2. Update any other files that import from `debug_summary_callback`
3. Update any files that import `bedrock_auto_router`

### Phase 3: Document Changes
1. Update `README.md` with new paths
2. Create `docs/architecture.md` explaining the structure
3. Update `AGENTS.md` with new refactor guidelines

### Phase 4: Cleanup
1. Create symlinks in root for shell scripts
2. Delete old `debug_summary_callback.py` and `debug_summary_callback/` folder
3. Move/merge `vscode_context.py` into `src/core/_vscode_context.py`
4. Remove `__pycache__` directories

## Implementation Notes

### Public API Preservation
- `proxy_handler_instance` from `callbacks` remains public
- `BedrockAutoRouter` class remains importable via `src.core.router`
- Update `AGENTS.md` to reference new `src/callbacks/handler.py`

### Backward Compatibility
- Create minimal backward compat layer if needed:
  ```python
  # debug_summary_callback.py (legacy, redirects to src.callbacks.handler)
  from src.callbacks.handler import DebugSummaryHandler, proxy_handler_instance
  ```

### Testing Strategy
- Add tests for `core/router.py` (routing logic)
- Add tests for `callbacks/` (logging, cost calculation)
- Integration tests for end-to-end flow

### Docker Impact
- Update `Dockerfile` to copy `src/` instead of root `.py` files
- Consider using `pyproject.toml` for dependency installation

## Benefits

1. **Professional appearance**: Industry-standard structure
2. **Easier onboarding**: New developers understand layout quickly
3. **Better testing**: Clear module boundaries
4. **Scalability**: Easy to add new features
5. **Maintainability**: Smaller, focused files
6. **Deduplication**: Shared VS Code logic in one place

## Risk Mitigation

1. **Test before merging**: Run `./verify-proxy.sh` after changes
2. **Gradual migration**: Keep legacy imports until all updated
3. **CI/CD integration**: Add linting/type checking in workflow
4. **Documentation**: Update all docs including AGENTS.md
