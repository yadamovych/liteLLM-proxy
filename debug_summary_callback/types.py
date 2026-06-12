"""Type definitions for structured data in debug_summary_callback."""

from __future__ import annotations

from typing import TypedDict


class RouteInfo(TypedDict):
    """Type for route metadata from bedrock_auto_router."""
    tier: str
    score: float | None
    stripped_chars: int | None
    intent: str | None
    signals: list[str] | None


class UsageStats(TypedDict):
    """Type for token usage statistics."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class ModelInfo(TypedDict):
    """Type for model identification."""
    actual: str
    via: str | None


class RequestSummary(TypedDict):
    """Type for request summary information."""
    msgs: int | None
    roles: str | None
    last: str | None
    source: str | None