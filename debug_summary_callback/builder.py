"""DebugLogBuilder class for building debug log entries."""

from __future__ import annotations

from typing import Any

from .types import RequestSummary, RouteInfo, UsageStats
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
        """Initialize the builder.
        
        Args:
            debug_enabled: Whether debug logging is enabled
            cost_footer_enabled: Whether to include cost footer in responses
            max_log_intent: Maximum length for logged intent strings
        """
        self.debug_enabled = debug_enabled
        self.cost_footer_enabled = cost_footer_enabled
        self.max_log_intent = max_log_intent

    def extract_request_info(self, kwargs: dict, payload: dict | None) -> RequestSummary:
        """Extract request summary from kwargs and payload.
        
        Args:
            kwargs: The original request kwargs
            payload: The standard logging object payload
            
        Returns:
            RequestSummary dict with message count, roles, and last user message
        """
        return extract_request_summary(kwargs, payload)

    def extract_route_info(self, kwargs: dict, payload: dict | None) -> RouteInfo | None:
        """Extract route metadata from request.
        
        Args:
            kwargs: The original request kwargs
            payload: The standard logging object payload
            
        Returns:
            RouteInfo if route metadata exists, None otherwise
        """
        route = self._extract_route_raw(kwargs, payload)
        if not route:
            return None
        return RouteInfo(
            tier=route.get("tier", ""),
            score=route.get("score"),
            stripped_chars=route.get("stripped_chars"),
            intent=route.get("intent"),
            signals=None,
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
        """Build a complete debug log entry.
        
        Args:
            kwargs: The original request kwargs
            response_obj: The response object
            payload: The standard logging object payload
            usage: Extracted usage statistics
            duration_ms: Request duration in milliseconds
            route_info: Extracted route metadata
            
        Returns:
            Dict with all fields for the debug log entry
        """
        model_info = self._extract_model_info(kwargs, payload, response_obj)
        
        log_parts: dict[str, Any] = {
            "model": model_info["actual"],
            "duration_ms": duration_ms,
        }
        
        if model_info["via"]:
            log_parts["via"] = model_info["via"]
        
        if route_info:
            if route_info["tier"]:
                log_parts["route"] = route_info["tier"]
            if route_info["score"] is not None:
                log_parts["route_score"] = route_info["score"]
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
        """Extract model name and routing info.
        
        Args:
            kwargs: The original request kwargs
            payload: The standard logging object payload
            response_obj: The response object
            
        Returns:
            ModelInfo dict with actual model name and optional routing path
        """
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
        if via == "bedrock-auto" and actual in {"claude-haiku", "claude-sonnet"}:
            return ModelInfo(actual=actual, via=via)
        if via and actual == "unknown":
            return ModelInfo(actual=via)
        return ModelInfo(actual=actual, via=via)

    def _extract_route_raw(self, kwargs: dict, payload: dict | None) -> dict[str, Any] | None:
        """Extract raw route metadata dict.
        
        Args:
            kwargs: The original request kwargs
            payload: The standard logging object payload
            
        Returns:
            Route metadata dict if found, None otherwise
        """
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