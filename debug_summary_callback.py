"""LiteLLM proxy callback: debug logs + optional per-request cost footer in responses."""

from __future__ import annotations

import os
import re
import sys
from typing import Any, AsyncGenerator, Optional

import bedrock_auto_router  # noqa: F401 — VS Code-aware complexity router patch

from litellm.integrations.custom_logger import CustomLogger
from litellm.types.utils import Delta, ModelResponseStream, StreamingChoices

_COPILOT_MARKERS = ("<context>", "<editorContext>", "<attachments>", "<toolResults>")

_KNOWN_ALIASES = frozenset(
    {"claude-haiku", "claude-sonnet", "bedrock-auto", "nova-lite", "qwen3-32b", "qwen3-coder"}
)

_ALIAS_RULES: tuple[tuple[str, str], ...] = (
    ("haiku", "claude-haiku"),
    ("sonnet", "claude-sonnet"),
    ("nova", "nova-lite"),
    ("coder", "qwen3-coder"),
    ("qwen", "qwen3-32b"),
)

_USAGE_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


class _ModelInfo:
    __slots__ = ("actual", "via")

    def __init__(self, actual: str, via: Optional[str] = None) -> None:
        self.actual = actual
        self.via = via

    @property
    def display(self) -> str:
        return self.via or self.actual


def _debug_enabled() -> bool:
    if os.environ.get("LITELLM_LOG", "").upper() in {"DEBUG", "TRACE"}:
        return True
    return os.environ.get("LITELLM_DEBUG", "").lower() in {"1", "true", "yes", "on"}


def _cost_footer_enabled() -> bool:
    return os.environ.get("LITELLM_COST_FOOTER", "1").lower() in {"1", "true", "yes", "on"}


def _truncate(text: str, limit: int = 72) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif "text" in block:
                    parts.append(str(block["text"]))
            else:
                parts.append(str(block))
        return " ".join(parts)
    return str(content)


def _role_counts(messages: list) -> str:
    counts: dict[str, int] = {}
    for msg in messages:
        if isinstance(msg, dict):
            role = str(msg.get("role", "?"))
            counts[role] = counts.get(role, 0) + 1
    return ",".join(f"{r}:{c}" for r, c in counts.items()) if counts else "none"


def _is_copilot_payload(text: str) -> bool:
    lowered = text.lstrip().lower()
    return any(m.lower() in lowered for m in _COPILOT_MARKERS)


def _user_snippet(text: str) -> Optional[str]:
    text = text.strip()
    if not text or _is_copilot_payload(text):
        return None
    return _truncate(text)


def _summarize_request(kwargs: dict, payload: Optional[dict]) -> dict[str, Any]:
    messages = kwargs.get("messages") or (payload or {}).get("messages")

    if isinstance(messages, str):
        return {"last": _truncate(messages)}
    if not isinstance(messages, list):
        return {}

    last_user = ""
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            last_user = _message_text(msg.get("content"))

    fields: dict[str, Any] = {"msgs": len(messages), "roles": _role_counts(messages)}
    if last_user and _is_copilot_payload(last_user):
        fields["source"] = "vscode"
    elif snippet := _user_snippet(last_user):
        fields["last"] = snippet
    return fields


def _int_field(obj: Any, *names: str) -> int:
    for name in names:
        if obj is None:
            continue
        value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
        if value is not None:
            return int(value)
    return 0


def _usage_from_object(usage: Any) -> dict[str, int]:
    if usage is None:
        return {}

    if isinstance(usage, dict):
        source, details = usage, usage.get("prompt_tokens_details")
    elif hasattr(usage, "model_dump"):
        source = usage.model_dump()
        details = source.get("prompt_tokens_details") or getattr(
            usage, "prompt_tokens_details", None
        )
    else:
        source, details = {}, getattr(usage, "prompt_tokens_details", None)

    return {
        "prompt_tokens": _int_field(source, "prompt_tokens") or _int_field(usage, "prompt_tokens"),
        "completion_tokens": (
            _int_field(source, "completion_tokens") or _int_field(usage, "completion_tokens")
        ),
        "total_tokens": _int_field(source, "total_tokens") or _int_field(usage, "total_tokens"),
        "cache_read_input_tokens": max(
            _int_field(source, "cache_read_input_tokens"),
            _int_field(usage, "_cache_read_input_tokens", "cache_read_input_tokens"),
            _int_field(details, "cached_tokens"),
        ),
        "cache_creation_input_tokens": max(
            _int_field(source, "cache_creation_input_tokens"),
            _int_field(usage, "_cache_creation_input_tokens", "cache_creation_input_tokens"),
            _int_field(details, "cache_creation_tokens"),
        ),
    }


def _merge_usage(*sources: dict[str, int]) -> dict[str, int]:
    merged: dict[str, int] = {k: 0 for k in _USAGE_KEYS}
    for src in sources:
        for key in _USAGE_KEYS:
            merged[key] = max(merged[key], src.get(key, 0))
    return merged


def _extract_usage(kwargs: dict, payload: Optional[dict], response_obj: Any) -> dict[str, int]:
    sources: list[dict[str, int]] = []

    if payload:
        sources.append(
            _usage_from_object(
                {k: payload.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
            )
        )

    response_usage = getattr(response_obj, "usage", None) or (
        response_obj.get("usage") if isinstance(response_obj, dict) else None
    )
    sources.append(_usage_from_object(response_usage))
    sources.append(_usage_from_object(kwargs.get("combined_usage_object")))

    usage = _merge_usage(*sources)
    if not usage.get("total_tokens"):
        usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    return usage


def _short_bedrock_model(model: str) -> str:
    if "/" in model:
        model = model.rsplit("/", 1)[-1]
    if model.startswith("eu.anthropic."):
        name = model.removeprefix("eu.anthropic.")
        if name.startswith("claude-"):
            return name.split("-202", 1)[0]
    return model


def _resolve_model_alias(model: str) -> str:
    lowered = model.lower()
    if lowered in _KNOWN_ALIASES:
        return model
    for substring, alias in _ALIAS_RULES:
        if substring in lowered:
            return alias
    return _short_bedrock_model(model)


def _extract_model_info(
    kwargs: dict, payload: Optional[dict], response_obj: Any
) -> _ModelInfo:
    via: Optional[str] = None
    if payload and payload.get("model_group"):
        via = _resolve_model_alias(str(payload["model_group"]))

    actual_raw = (
        (payload or {}).get("model")
        or (response_obj.get("model") if isinstance(response_obj, dict) else None)
        or getattr(response_obj, "model", None)
        or kwargs.get("model")
        or ""
    )
    actual = _resolve_model_alias(str(actual_raw)) if actual_raw else "unknown"

    if via == actual:
        via = None
    if via == "bedrock-auto" and actual in {"claude-haiku", "claude-sonnet"}:
        return _ModelInfo(actual=actual, via=via)
    if via and actual == "unknown":
        return _ModelInfo(actual=via)
    return _ModelInfo(actual=actual, via=via)


def _auto_route_meta(kwargs: dict, payload: Optional[dict]) -> dict[str, Any]:
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
    return {}


def _proxy_cache_hit(kwargs: dict, payload: Optional[dict]) -> bool:
    return kwargs.get("cache_hit") is True or bool(payload and payload.get("cache_hit") is True)


def _request_has_cache_control(kwargs: dict, payload: Optional[dict]) -> bool:
    messages = kwargs.get("messages") or (payload or {}).get("messages")
    if not isinstance(messages, list):
        return False
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("cache_control"):
            return True
        content = msg.get("content")
        if isinstance(content, list):
            if any(isinstance(b, dict) and b.get("cache_control") for b in content):
                return True
    return False


def _cache_log_fields(
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


def _chunk_as_dict(chunk: Any) -> dict[str, Any]:
    if isinstance(chunk, dict):
        return chunk
    return chunk.model_dump() if hasattr(chunk, "model_dump") else {}


def _choice_dict(chunk_dict: dict[str, Any]) -> dict[str, Any]:
    choices = chunk_dict.get("choices") or []
    if not choices:
        return {}
    choice = choices[0]
    if isinstance(choice, dict):
        return choice
    return choice.model_dump() if hasattr(choice, "model_dump") else {}


def _usage_dict_from_chunk(chunk_dict: dict[str, Any]) -> dict[str, int]:
    usage = chunk_dict.get("usage")
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    return _usage_from_object(usage) if isinstance(usage, dict) else {}


def _display_model_name(
    kwargs: dict,
    payload: Optional[dict],
    *,
    stream_model: Optional[str] = None,
) -> str:
    response_stub: dict[str, Any] = {"model": stream_model} if stream_model else {}
    return _extract_model_info(kwargs, payload, response_stub).display


def _compute_cost_usd(
    *,
    usage: dict[str, int],
    request_data: Optional[dict],
    kwargs: Optional[dict] = None,
    payload: Optional[dict] = None,
    proxy_hit: bool = False,
) -> Optional[float]:
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
            model=model,
            custom_llm_provider="bedrock",
            region_name=region,
        )
        if cost is not None:
            return float(cost)
    except Exception:
        pass
    return None


def _format_usd(cost: Optional[float]) -> str:
    if cost is None:
        return "n/a"
    if cost == 0:
        return "$0.000000"
    return f"${cost:.6f}" if cost < 0.0001 else f"${cost:.4f}"


def _format_token_count(value: int) -> str:
    return f"{value:,}"


def _strip_existing_footer(content: Any) -> Any:
    if isinstance(content, str):
        match = re.search(r"\n\n---\n\*\$[^\*]+\*$", content)
        if match:
            return content[: match.start()]
        return content
    if isinstance(content, list):
        if not content:
            return content
        last = content[-1]
        if isinstance(last, dict) and last.get("type") == "text":
            text = str(last.get("text", ""))
            match = re.search(r"\n\n---\n\*\$[^\*]+\*$", text)
            if match:
                content = [*content[:-1], {**last, "text": text[: match.start()]}]
            return content
    return content


def _build_cost_footer(
    *,
    usage: dict[str, int],
    model_name: str,
    cost_usd: Optional[float],
    proxy_hit: bool = False,
) -> str:
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)

    parts = [_format_usd(cost_usd), model_name]
    if proxy_hit:
        parts.append("proxy-cache")
    parts.append(f"{_format_token_count(prompt_tokens)} in")
    parts.append(f"{_format_token_count(completion_tokens)} out")
    if cache_read > 0:
        parts.append(f"{_format_token_count(cache_read)} cached")

    return "\n\n---\n*" + " · ".join(parts) + "*"


def _make_stream_footer_chunk(footer: str, stream_meta: dict[str, Any]) -> ModelResponseStream:
    return ModelResponseStream(
        id=stream_meta.get("id"),
        created=stream_meta.get("created"),
        model=stream_meta.get("model"),
        choices=[StreamingChoices(index=0, delta=Delta(content=footer))],
    )


def _append_footer_to_message_content(content: Any, footer: str) -> Any:
    if isinstance(content, str):
        return content + footer
    if isinstance(content, list):
        if not content:
            return [{"type": "text", "text": footer.lstrip()}]
        last = content[-1]
        if isinstance(last, dict) and last.get("type") == "text":
            return [*content[:-1], {**last, "text": str(last.get("text", "")) + footer}]
    return content


def _format_field(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return f"{key}={str(value).lower()}"
    if isinstance(value, (int, float)):
        return f"{key}={value}"
    if isinstance(value, str):
        if " " in value or '"' in value:
            return f'{key}="{value.replace(chr(34), chr(39))}"'
        return f"{key}={value}"
    return f"{key}={value}"


def _emit(level: str, parts: dict[str, Any]) -> None:
    body = " ".join(_format_field(k, v) for k, v in parts.items())
    stream = sys.stderr if level == "error" else sys.stdout
    print(f"[litellm:{level}] {body}", file=stream, flush=True)


def _log_success(kwargs: dict, response_obj: Any, start_time, end_time) -> None:
    if not _debug_enabled():
        return

    payload = kwargs.get("standard_logging_object")
    if payload is not None and not isinstance(payload, dict):
        payload = None

    info = _extract_model_info(kwargs, payload, response_obj)
    usage = _extract_usage(kwargs, payload, response_obj)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)
    if payload and payload.get("response_time") is not None:
        duration_ms = int(float(payload["response_time"]) * 1000)

    log_parts: dict[str, Any] = {"model": info.actual}
    if info.via:
        log_parts["via"] = info.via

    route = _auto_route_meta(kwargs, payload)
    if route:
        log_parts["route"] = route.get("tier")
        if route.get("score") is not None:
            log_parts["route_score"] = route["score"]
        if route.get("stripped_chars") is not None:
            log_parts["intent_chars"] = route["stripped_chars"]
        if route.get("intent"):
            log_parts["intent"] = _truncate(str(route["intent"]), 48)

    log_parts.update(
        {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "duration_ms": duration_ms,
        }
    )
    log_parts.update(_summarize_request(kwargs, payload))

    saved_cache_cost = (
        float(payload["saved_cache_cost"])
        if payload and payload.get("saved_cache_cost") is not None
        else 0.0
    )
    proxy_hit = _proxy_cache_hit(kwargs, payload)
    log_parts.update(
        _cache_log_fields(
            usage,
            proxy_hit=proxy_hit,
            cache_requested=_request_has_cache_control(kwargs, payload),
            saved_cache_cost=saved_cache_cost,
        )
    )

    cost_usd: Optional[float] = None
    if payload and payload.get("response_cost") is not None:
        cost_usd = float(payload["response_cost"])
    elif usage.get("prompt_tokens", 0) or usage.get("completion_tokens", 0):
        cost_usd = _compute_cost_usd(
            usage=usage, request_data=None, kwargs=kwargs, payload=payload, proxy_hit=proxy_hit
        )
    if cost_usd is not None:
        log_parts["cost_usd"] = round(cost_usd, 6)

    _emit("debug", log_parts)


def _log_failure(kwargs: dict, response_obj: Any) -> None:
    if not _debug_enabled():
        return

    payload = kwargs.get("standard_logging_object")
    if payload is not None and not isinstance(payload, dict):
        payload = None

    info = _extract_model_info(kwargs, payload, response_obj)
    error = kwargs.get("exception")
    parts: dict[str, Any] = {
        "model": info.actual,
        "error": _truncate(str(error) if error else str(response_obj), 120),
    }
    if info.via:
        parts["via"] = info.via
    parts.update(_summarize_request(kwargs, payload))
    _emit("error", parts)


class DebugSummaryHandler(CustomLogger):
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        _log_success(kwargs, response_obj, start_time, end_time)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        _log_success(kwargs, response_obj, start_time, end_time)

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        _log_failure(kwargs, response_obj)

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        _log_failure(kwargs, response_obj)

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        if not _cost_footer_enabled():
            return response

        usage = _usage_from_object(getattr(response, "usage", None))
        if not usage.get("prompt_tokens") and not usage.get("completion_tokens"):
            return response

        choices = getattr(response, "choices", None) or []
        if not choices:
            return response
        message = getattr(choices[0], "message", None)
        if message is None or getattr(message, "tool_calls", None):
            return response

        payload = data.get("standard_logging_object")
        if payload is not None and not isinstance(payload, dict):
            payload = None
        proxy_hit = bool(data.get("cache_hit"))
        message.content = _strip_existing_footer(message.content)
        footer = _build_cost_footer(
            usage=usage,
            model_name=_display_model_name(data, payload),
            cost_usd=_compute_cost_usd(
                usage=usage,
                request_data=data,
                kwargs=data,
                payload=payload,
                proxy_hit=proxy_hit,
            ),
            proxy_hit=proxy_hit,
        )
        message.content = _append_footer_to_message_content(message.content, footer)
        return response

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict,
        response,
        request_data: dict,
    ) -> AsyncGenerator[Any, None]:
        if not _cost_footer_enabled():
            async for chunk in response:
                yield chunk
            return

        last_finish_reason: Optional[str] = None
        stream_meta: dict[str, Any] = {}
        proxy_hit = bool(request_data.get("cache_hit"))

        async for chunk in response:
            chunk_dict = _chunk_as_dict(chunk)
            usage = _usage_dict_from_chunk(chunk_dict)

            if chunk_dict.get("id"):
                stream_meta["id"] = chunk_dict["id"]
            if chunk_dict.get("model"):
                stream_meta["model"] = chunk_dict["model"]
            if chunk_dict.get("created"):
                stream_meta["created"] = chunk_dict["created"]

            choice = _choice_dict(chunk_dict)
            if choice.get("finish_reason"):
                last_finish_reason = str(choice["finish_reason"])

            yield chunk

        if last_finish_reason and usage and last_finish_reason != "tool_calls":
            payload = request_data.get("standard_logging_object")
            if payload is not None and not isinstance(payload, dict):
                payload = None
            footer = _build_cost_footer(
                usage=usage,
                model_name=_display_model_name(
                    request_data,
                    payload,
                    stream_model=stream_meta.get("model"),
                ),
                cost_usd=_compute_cost_usd(
                    usage=usage,
                    request_data=request_data,
                    kwargs=request_data,
                    payload=payload,
                    proxy_hit=proxy_hit,
                ),
                proxy_hit=proxy_hit,
            )
            yield _make_stream_footer_chunk(footer, stream_meta)


proxy_handler_instance = DebugSummaryHandler()
