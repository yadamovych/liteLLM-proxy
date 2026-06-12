"""Shared utility functions for debug_summary_callback."""

from __future__ import annotations

import re
from typing import Any

from vscode_context import is_copilot_payload

USAGE_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)
_SQUEEZE_WS = re.compile(r"\s+")


def truncate(text: str, limit: int = 72) -> str:
    """Truncate text to a maximum length, squeezing whitespace.
    
    Args:
        text: The text to truncate
        limit: Maximum length including ellipsis
        
    Returns:
        Truncated text with "..." appended if needed
    """
    text = _SQUEEZE_WS.sub(" ", text).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def extract_int_field(obj: Any, *names: str) -> int:
    """Extract an integer field from an object or dict.
    
    Args:
        obj: The object or dict to extract from
        *names: Field names to try in order
        
    Returns:
        The integer value, or 0 if not found
    """
    for name in names:
        if obj is None:
            continue
        value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
        if value is not None:
            return int(value)
    return 0


def extract_usage_from_object(usage: Any) -> dict[str, int]:
    """Extract usage stats from various object types.
    
    Args:
        usage: The usage object (dict, object with model_dump, or None)
        
    Returns:
        Dict with usage statistics
    """
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
        "prompt_tokens": extract_int_field(source, "prompt_tokens") or extract_int_field(usage, "prompt_tokens"),
        "completion_tokens": (
            extract_int_field(source, "completion_tokens") or extract_int_field(usage, "completion_tokens")
        ),
        "total_tokens": extract_int_field(source, "total_tokens") or extract_int_field(usage, "total_tokens"),
        "cache_read_input_tokens": max(
            extract_int_field(source, "cache_read_input_tokens"),
            extract_int_field(usage, "_cache_read_input_tokens", "cache_read_input_tokens"),
            extract_int_field(details, "cached_tokens"),
        ),
        "cache_creation_input_tokens": max(
            extract_int_field(source, "cache_creation_input_tokens"),
            extract_int_field(usage, "_cache_creation_input_tokens", "cache_creation_input_tokens"),
            extract_int_field(details, "cache_creation_tokens"),
        ),
    }


def merge_usage(*sources: dict[str, int]) -> dict[str, int]:
    """Merge multiple usage dicts, taking the max for each key.
    
    Args:
        *sources: Multiple usage dicts to merge
        
    Returns:
        Merged dict with max values for each usage key
    """
    merged: dict[str, int] = {k: 0 for k in USAGE_KEYS}
    for src in sources:
        for key in USAGE_KEYS:
            merged[key] = max(merged[key], src.get(key, 0))
    return merged


def extract_usage(kwargs: dict, payload: dict | None, response_obj: Any) -> dict[str, int]:
    """Extract usage statistics from request/response.
    
    Searches multiple sources and returns max values for each metric to
    handle partial data.
    
    Args:
        kwargs: The original request kwargs
        payload: The standard logging object payload
        response_obj: The response object
        
    Returns:
        Dict with usage statistics
    """
    sources: list[dict[str, int]] = []

    if payload:
        sources.append(
            extract_usage_from_object(
                {k: payload.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
            )
        )

    response_usage = getattr(response_obj, "usage", None) or (
        response_obj.get("usage") if isinstance(response_obj, dict) else None
    )
    sources.append(extract_usage_from_object(response_usage))
    sources.append(extract_usage_from_object(kwargs.get("combined_usage_object")))

    usage = merge_usage(*sources)
    if not usage.get("total_tokens"):
        usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    return usage


def message_text(content: Any) -> str:
    """Extract text content from a message.
    
    Handles string, dict, list of dicts, andNone.
    
    Args:
        content: The message content
        
    Returns:
        Extracted text as a single string
    """
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


def role_counts(messages: list) -> str:
    """Count messages by role.
    
    Args:
        messages: List of message dicts
        
    Returns:
        Comma-separated "role:count" strings
    """
    counts: dict[str, int] = {}
    for msg in messages:
        if isinstance(msg, dict):
            role = str(msg.get("role", "?"))
            counts[role] = counts.get(role, 0) + 1
    return ",".join(f"{r}:{c}" for r, c in counts.items()) if counts else "none"


def user_snippet(text: str) -> str | None:
    """Extract a user message snippet, excluding Copilot payloads.
    
    Args:
        text: The raw user message text
        
    Returns:
        Truncated snippet, or None if Copilot payload or empty
    """
    text = text.strip()
    if not text or is_copilot_payload(text):
        return None
    return truncate(text)


def extract_request_summary(kwargs: dict, payload: dict | None) -> dict[str, Any]:
    """Extract a summary of the request for logging.
    
    Args:
        kwargs: The original request kwargs
        payload: The standard logging object payload
        
    Returns:
        Dict with request summary info (msgs, roles, last, source)
    """
    messages = kwargs.get("messages") or (payload or {}).get("messages")

    if isinstance(messages, str):
        return {"last": truncate(messages)}
    if not isinstance(messages, list):
        return {}

    last_user = ""
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            last_user = message_text(msg.get("content"))

    fields: dict[str, Any] = {"msgs": len(messages), "roles": role_counts(messages)}
    if last_user and is_copilot_payload(last_user):
        fields["source"] = "vscode"
    elif snippet := user_snippet(last_user):
        fields["last"] = snippet
    return fields


def normalize_model_name(model: str) -> str:
    """Normalize a model name to its canonical form.
    
    Handles Bedrock ARN prefixes, model aliases, and known patterns.
    
    Args:
        model: The raw model name
        
    Returns:
        The normalized model name
    """
    if not model:
        return "unknown"
    
    if "/" in model:
        model = model.rsplit("/", 1)[-1]
    if model.startswith("eu.anthropic."):
        name = model.removeprefix("eu.anthropic.")
        if name.startswith("claude-"):
            return name.split("-202", 1)[0]
    
    _KNOWN_ALIASES = frozenset(
        {"claude-haiku", "claude-sonnet", "bedrock-auto", "nova-lite", "qwen3-32b", "qwen3-coder"}
    )
    _ALIAS_RULES = {
        "haiku": "claude-haiku",
        "sonnet": "claude-sonnet",
        "nova": "nova-lite",
        "coder": "qwen3-coder",
        "qwen": "qwen3-32b",
    }
    
    lowered = model.lower()
    if lowered in _KNOWN_ALIASES:
        return model
    for substring, alias in _ALIAS_RULES.items():
        if substring in lowered:
            return alias
    return model


def strip_existing_footer(content: Any) -> Any:
    """Remove an existing cost footer from message content.
    
    Args:
        content: The message content (str or list)
        
    Returns:
        Content with footer removed if present
    """
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


def append_footer_to_message_content(content: Any, footer: str) -> Any:
    """Append a cost footer to message content.
    
    Args:
        content: The message content (str or list)
        footer: The footer string to append
        
    Returns:
        Content with footer appended
    """
    if isinstance(content, str):
        return content + footer
    if isinstance(content, list):
        if not content:
            return [{"type": "text", "text": footer.lstrip()}]
        last = content[-1]
        if isinstance(last, dict) and last.get("type") == "text":
            return [*content[:-1], {**last, "text": str(last.get("text", "")) + footer}]
    return content