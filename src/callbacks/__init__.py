"""Multi-file package for debug summary callback functionality."""

from .builder import DebugLogBuilder
from .cost import build_cost_footer, compute_cost_usd, format_cost, format_token_count
from .handler import DebugSummaryHandler, proxy_handler_instance
from .routes import extract_cache_stats, extract_route_metadata
from .streams import StreamMetadataAccumulator, accumulate_stream_usage, inject_footer_into_stream
from .types import ModelInfo, RequestSummary, RouteInfo, UsageStats
from .utils import (
    append_footer_to_message_content,
    extract_int_field,
    extract_request_summary,
    extract_usage,
    extract_usage_from_object,
    is_copilot_payload,
    merge_usage,
    message_text,
    normalize_model_name,
    role_counts,
    strip_existing_footer,
    truncate,
    user_snippet,
)

__all__ = [
    "DebugLogBuilder",
    "build_cost_footer",
    "compute_cost_usd",
    "format_cost",
    "format_token_count",
    "DebugSummaryHandler",
    "proxy_handler_instance",
    "extract_cache_stats",
    "extract_route_metadata",
    "StreamMetadataAccumulator",
    "accumulate_stream_usage",
    "inject_footer_into_stream",
    "ModelInfo",
    "RequestSummary",
    "RouteInfo",
    "UsageStats",
    "append_footer_to_message_content",
    "extract_int_field",
    "extract_request_summary",
    "extract_usage",
    "extract_usage_from_object",
    "is_copilot_payload",
    "merge_usage",
    "message_text",
    "normalize_model_name",
    "role_counts",
    "strip_existing_footer",
    "truncate",
    "user_snippet",
]
