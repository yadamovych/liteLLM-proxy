"""Core routing logic for litellm-bedrock."""

from .router import BedrockAutoRouter, apply_patch

__all__ = ["BedrockAutoRouter", "apply_patch"]
