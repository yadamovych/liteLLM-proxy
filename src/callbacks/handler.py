"""DebugSummaryHandler class for LiteLLM callback integration."""

from __future__ import annotations

import core.router  # noqa: F401 — bedrock-auto complexity routing patch

import time
from typing import Any

from litellm.integrations.custom_logger import CustomLogger
from litellm.types.utils import Delta, ModelResponseStream, StreamingChoices

from .builder import DebugLogBuilder
from .cost import compute_cost_usd, format_cost, format_token_count, build_cost_footer
from .routes import extract_route_metadata, extract_cache_stats
from .streams import (
    StreamMetadataAccumulator,
    inject_footer_into_stream,
    accumulate_stream_usage,
)
from .types import RequestSummary, RouteInfo, UsageStats, ModelInfo
from .utils import (
    truncate,
    extract_request_summary,
    extract_usage,
    normalize_model_name,
    is_copilot_payload,
    strip_existing_footer,
    append_footer_to_message_content,
    extract_usage_from_object,
)


def _debug_enabled() -> bool:
    import os
    if os.environ.get("LITELLM_LOG", "").upper() in {"DEBUG", "TRACE"}:
        return True
    return os.environ.get("LITELLM_DEBUG", "").lower() in {"1", "true", "yes", "on"}


def _cost_footer_enabled() -> bool:
    import os
    return os.environ.get("LITELLM_COST_FOOTER", "1").lower() in {"1", "true", "yes", "on"}


class DebugSummaryHandler(CustomLogger):
    def __init__(self) -> None:
        self.debug_enabled = _debug_enabled()
        self.cost_footer_enabled = _cost_footer_enabled()
        self._builder = DebugLogBuilder(
            debug_enabled=self.debug_enabled,
            cost_footer_enabled=self.cost_footer_enabled,
        )

    def log_success_event(
        self,
        kwargs: dict,
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        if not self.debug_enabled:
            return

        payload = kwargs.get("standard_logging_object")
        if payload is not None and not isinstance(payload, dict):
            payload = None

        route_info = self._builder.extract_route_info(kwargs, payload)
        usage = extract_usage(kwargs, payload, response_obj)
        
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        if payload and payload.get("response_time") is not None:
            duration_ms = int(float(payload["response_time"]) * 1000)

        saved_cache_cost = (
            float(payload["saved_cache_cost"])
            if payload and payload.get("saved_cache_cost") is not None
            else 0.0
        )
        proxy_hit = payload.get("cache_hit") is True if payload else False
        
        log_entry = self._builder.build_debug_log_entry(
            kwargs=kwargs,
            response_obj=response_obj,
            payload=payload,
            usage=usage,
            duration_ms=duration_ms,
            route_info=route_info,
        )
        
        cache_requested = self._request_has_cache_control(kwargs, payload)
        cache_stats = extract_cache_stats(
            usage,
            proxy_hit=proxy_hit,
            cache_requested=cache_requested,
            saved_cache_cost=saved_cache_cost,
        )
        log_entry.update(cache_stats)

        cost_usd = None
        if payload and payload.get("response_cost") is not None:
            cost_usd = float(payload["response_cost"])
        elif usage.get("prompt_tokens", 0) or usage.get("completion_tokens", 0):
            cost_usd = compute_cost_usd(
                usage=usage,
                request_data=None,
                kwargs=kwargs,
                payload=payload,
                proxy_hit=proxy_hit,
            )
        if cost_usd is not None:
            log_entry["cost_usd"] = round(cost_usd, 6)

        self._emit("debug", log_entry)

    async def async_log_success_event(
        self,
        kwargs: dict,
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        self.log_success_event(kwargs, response_obj, start_time, end_time)

    def log_failure_event(
        self,
        kwargs: dict,
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        if not self.debug_enabled:
            return

        payload = kwargs.get("standard_logging_object")
        if payload is not None and not isinstance(payload, dict):
            payload = None

        model_info = self._builder._extract_model_info(kwargs, payload, response_obj)
        error = kwargs.get("exception")
        parts: dict[str, Any] = {
            "model": model_info["actual"],
            "error": truncate(str(error) if error else str(response_obj), 120),
        }
        if model_info["via"]:
            parts["via"] = model_info["via"]
        parts.update(extract_request_summary(kwargs, payload))
        self._emit("error", parts)

    async def async_log_failure_event(
        self,
        kwargs: dict,
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        self.log_failure_event(kwargs, response_obj, start_time, end_time)

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: Any,
        response: Any,
    ) -> Any:
        if not self.cost_footer_enabled:
            return response

        usage = extract_usage_from_object(getattr(response, "usage", None))
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
        message.content = strip_existing_footer(message.content)
        footer = build_cost_footer(
            usage=usage,
            model_name=self._display_model_name(data, payload),
            cost_usd=compute_cost_usd(
                usage=usage,
                request_data=data,
                kwargs=data,
                payload=payload,
                proxy_hit=proxy_hit,
            ),
            proxy_hit=proxy_hit,
        )
        message.content = append_footer_to_message_content(message.content, footer)
        return response

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict: Any,
        response: Any,
        request_data: dict,
    ) -> Any:
        if not self.cost_footer_enabled:
            async for chunk in response:
                yield chunk
            return

        payload = request_data.get("standard_logging_object")
        if payload is not None and not isinstance(payload, dict):
            payload = None
        proxy_hit = bool(request_data.get("cache_hit"))

        async for chunk in inject_footer_into_stream(
            response=response,
            request_data=request_data,
            payload=payload,
            proxy_hit=proxy_hit,
        ):
            yield chunk

    def _request_has_cache_control(
        self,
        kwargs: dict,
        payload: dict | None,
    ) -> bool:
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

    def _display_model_name(
        self,
        kwargs: dict,
        payload: dict | None,
        *,
        stream_model: str | None = None,
    ) -> str:
        response_stub: dict[str, Any] = {"model": stream_model} if stream_model else {}
        model_info = self._builder._extract_model_info(kwargs, payload, response_stub)
        return model_info.get("via") or model_info.get("actual") or "unknown"

    def _emit(self, level: str, parts: dict[str, Any]) -> None:
        import sys
        body = " ".join(self._format_field(k, v) for k, v in parts.items())
        stream = sys.stderr if level == "error" else sys.stdout
        print(f"[litellm:{level}] {body}", file=stream, flush=True)

    def _format_field(self, key: str, value: Any) -> str:
        if isinstance(value, bool):
            return f"{key}={str(value).lower()}"
        if isinstance(value, (int, float)):
            return f"{key}={value}"
        if isinstance(value, str):
            if " " in value or '"' in value:
                return f'{key}="{value.replace(chr(34), chr(39))}"'
            return f"{key}={value}"
        return f"{key}={value}"


proxy_handler_instance = DebugSummaryHandler()
