"""DebugLogBuilder class for building debug log entries."""

from __future__ import annotations

from typing import Any

from .types import ModelInfo, RequestSummary, RouteInfo, UsageStats
from .utils import extract_request_summary, normalize_model_name, truncate


class DebugLogBuilder:
    """Builder class for constructing debug log entries.
    
    Encapsulates the logic for extracting information from requests/responses
    and building structured debug log data.
    """

    def __init__(
        self,
        debug_enabled: bool = True,
        cost_footer_enabled: bool = True,
        max_log_intent: int = 48,
    ) -> None:
        self.debug_enabled = debug_enabled
        self.cost_footer_enabled = cost_footer_enabled
        self.max_log_intent = max_log_intent

    def extract_request_info(self, kwargs: dict, payload: dict | None) -> RequestSummary:
        return extract_request_summary(kwargs, payload)

    def extract_route_info(self, kwargs: dict, payload: dict | None) -> RouteInfo | None:
        route = self._extract_route_raw(kwargs, payload)
        if not route:
            return None
        return RouteInfo(
            tier=route.get("tier", ""),
            mode=route.get("mode"),
            score=route.get("score"),
            stripped_chars=route.get("intent_chars", route.get("stripped_chars")),
            intent=route.get("intent"),
            signals=route.get("signals"),
        )

    def build_debug_log_entry(
        self,
        kwargs: dict,
        response_obj: Any,
        payload: dict | None,
        usage: UsageStats,
        duration_ms: int,
        route_info: RouteInfo | None,
    ) -> dict[str, Any]:
        model_info = self._extract_model_info(kwargs, payload, response_obj)
        
        log_parts: dict[str, Any] = {
            "model": model_info["actual"],
            "duration_ms": duration_ms,
        }
        
        if model_info["via"]:
            log_parts["via"] = model_info["via"]
        
        if route_info:
            if route_info["mode"]:
                log_parts["mode"] = route_info["mode"]
            if route_info["tier"]:
                log_parts["route"] = route_info["tier"]
            if route_info["stripped_chars"] is not None:
                log_parts["intent_chars"] = route_info["stripped_chars"]
            if route_info["intent"]:
                log_parts["intent"] = truncate(route_info["intent"], self.max_log_intent)
        
        log_parts.update(usage)
        log_parts.update(extract_request_summary(kwargs, payload))
        
        return log_parts

    def _extract_model_info(
        self,
        kwargs: dict,
        payload: dict | None,
        response_obj: Any,
    ) -> ModelInfo:
        via: str | None = None
        if payload and payload.get("model_group"):
            via = normalize_model_name(str(payload["model_group"]))

        actual_raw = (
            (payload or {}).get("model")
            or (response_obj.get("model") if isinstance(response_obj, dict) else None)
            or getattr(response_obj, "model", None)
            or kwargs.get("model")
            or ""
        )
        actual = normalize_model_name(str(actual_raw)) if actual_raw else "unknown"

        if via == actual:
            via = None
        if via == "bedrock-auto" and actual in {
            "claude-haiku",
            "claude-sonnet",
            "qwen3-coder",
        }:
            return ModelInfo(actual=actual, via=via)
        if via and actual == "unknown":
            return ModelInfo(actual=via)
        return ModelInfo(actual=actual, via=via)

    def _extract_route_raw(self, kwargs: dict, payload: dict | None) -> dict[str, Any] | None:
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
