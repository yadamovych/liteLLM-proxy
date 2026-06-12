"""Cost calculation and formatting utilities."""

from __future__ import annotations

from typing import Any

from .utils import normalize_model_name


def compute_cost_usd(
    *,
    usage: dict[str, int],
    request_data: dict | None = None,
    kwargs: dict | None = None,
    payload: dict | None = None,
    proxy_hit: bool = False,
) -> float | None:
    if proxy_hit:
        return 0.0

    result = {"usage": usage}
    logging_obj = (request_data or {}).get("litellm_logging_obj")
    if logging_obj is not None:
        try:
            cost = logging_obj._response_cost_calculator(result=result, cache_hit=False)
            if cost is not None:
                return float(cost)
        except Exception:
            pass

    try:
        from litellm.cost_calculator import completion_cost

        model = (
            str((request_data or {}).get("model") or (request_data or {}).get("model_group") or "")
            or str((payload or {}).get("model") or (payload or {}).get("model_group") or "")
            or str((kwargs or {}).get("model") or "")
        )
        litellm_params = (request_data or {}).get("litellm_params") or {}
        region = litellm_params.get("aws_region_name") or "eu-central-1"
        cost = completion_cost(
            completion_response=result,
            model=normalize_model_name(model),
            custom_llm_provider="bedrock",
            region_name=region,
        )
        if cost is not None:
            return float(cost)
    except Exception:
        pass
    return None


def format_cost(cost: float | None) -> str:
    if cost is None:
        return "n/a"
    if cost == 0:
        return "$0.000000"
    return f"${cost:.6f}" if cost < 0.0001 else f"${cost:.4f}"


def format_token_count(value: int) -> str:
    return f"{value:,}"


def build_cost_footer(
    *,
    usage: dict[str, int],
    model_name: str,
    cost_usd: float | None,
    proxy_hit: bool = False,
) -> str:
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)

    parts = [format_cost(cost_usd), model_name]
    if proxy_hit:
        parts.append("proxy-cache")
    parts.append(f"{format_token_count(prompt_tokens)} in")
    parts.append(f"{format_token_count(completion_tokens)} out")
    if cache_read > 0:
        parts.append(f"{format_token_count(cache_read)} cached")

    return "\n\n---\n*" + " · ".join(parts) + "*"
