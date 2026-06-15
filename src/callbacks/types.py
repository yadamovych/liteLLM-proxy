"""Type definitions for LiteLLM proxy callback data."""

from __future__ import annotations

from typing import TypedDict


class RouteInfo(TypedDict):
    tier: str
    mode: str | None
    score: float | None
    stripped_chars: int | None
    intent: str | None
    signals: list[str] | None


class UsageStats(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class ModelInfo(TypedDict):
    actual: str
    via: str | None


class RequestSummary(TypedDict):
    msgs: int | None
    roles: str | None
    last: str | None
    source: str | None
