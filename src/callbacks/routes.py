"""Route metadata extraction utilities."""

from __future__ import annotations

from typing import Any


def extract_route_metadata(kwargs: dict, payload: dict | None) -> dict[str, Any] | None:
    for source in (
        kwargs.get("litellm_metadata"),
        kwargs.get("metadata"),
        (payload or {}).get("metadata"),
        (kwargs.get("litellm_params") or {}).get("metadata"),
        (kwargs.get("litellm_params") or {}).get("litellm_metadata"),
    ):
        if isinstance(source, dict):
            route = source.get("bedrock_auto_route")
            if isinstance(route, dict):
                return route
    return None


def extract_cache_stats(
    usage: dict[str, int],
    *,
    proxy_hit: bool,
    cache_requested: bool,
    saved_cache_cost: float = 0.0,
) -> dict[str, Any]:
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_write = usage.get("cache_creation_input_tokens", 0)
    prompt_tokens = usage.get("prompt_tokens", 0)

    fields: dict[str, Any] = {
        "proxy_cache": "hit" if proxy_hit else "miss",
        "cache_read": cache_read,
        "cache_write": cache_write,
    }
    if cache_requested:
        fields["cache_requested"] = True
    if prompt_tokens > 0 and cache_read > 0:
        fields["cache_hit_pct"] = round(100 * cache_read / prompt_tokens)
    if proxy_hit and saved_cache_cost > 0:
        fields["proxy_cache_saved_usd"] = round(saved_cache_cost, 6)
    return fields
