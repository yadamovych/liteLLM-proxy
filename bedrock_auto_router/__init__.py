"""VS Code-aware complexity router for bedrock-auto (strips Copilot context before scoring)."""

from __future__ import annotations

from .patch import apply_patch
from .router import BedrockAutoRouter

__all__ = ["BedrockAutoRouter", "apply_patch"]

apply_patch()
