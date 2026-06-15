"""Shared utility functions for debug_summary_callback."""

from __future__ import annotations

import re
from typing import Any

_COPILOT_MARKERS = ("<context>", "<editorContext>", "<attachments>", "<toolResults>")
_COPILOT_PATTERN = re.compile(r"|".join(re.escape(m) for m in _COPILOT_MARKERS), re.IGNORECASE)
USAGE_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)
_SQUEEZE_WS = re.compile(r"\s+")


def is_copilot_payload(text: str) -> bool:
    """Check if text appears to be a VS Code/Copilot payload based on markers.
    
    Args:
        text: The text content to check
        
    Returns:
        True if the text contains Copilot XML markers, False otherwise
    """
    if not text:
        return False
    lowered = text.lstrip().lower()
    return any(m.lower() in lowered for m in _COPILOT_MARKERS)


def has_vscode_code_context(text: str) -> bool:
    """Check if text contains VS Code code context markers.
    
    Args:
        text: The text content to check
        
    Returns:
        True if the text contains VS Code context markers, False otherwise
    """
    if not text:
        return False
    return bool(_COPILOT_PATTERN.search(text))


def strip_copilot_markers(text: str) -> str:
    """Remove Copilot XML markers from text.
    
    Args:
        text: The text to clean
        
    Returns:
        Text with Copilot markers removed
    """
    if not text or not is_copilot_payload(text):
        return text
    lowered = text.lstrip().lower()
    result = text
    for marker in _COPILOT_MARKERS:
        result = result.replace(marker, "")
    return result.strip()


def truncate(text: str, limit: int = 72) -> str:
    text = _SQUEEZE_WS.sub(" ", text).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def extract_int_field(obj: Any, *names: str) -> int:
    for name in names:
        if obj is None:
            continue
        value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
        if value is not None:
            return int(value)
    return 0


def extract_usage_from_object(usage: Any) -> dict[str, int]:
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
    merged: dict[str, int] = {k: 0 for k in USAGE_KEYS}
    for src in sources:
        for key in USAGE_KEYS:
            merged[key] = max(merged[key], src.get(key, 0))
    return merged


def extract_usage(kwargs: dict, payload: dict | None, response_obj: Any) -> dict[str, int]:
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
    counts: dict[str, int] = {}
    for msg in messages:
        if isinstance(msg, dict):
            role = str(msg.get("role", "?"))
            counts[role] = counts.get(role, 0) + 1
    return ",".join(f"{r}:{c}" for r, c in counts.items()) if counts else "none"


def user_snippet(text: str) -> str | None:
    text = text.strip()
    if not text or is_copilot_payload(text):
        return None
    return truncate(text)


def extract_request_summary(kwargs: dict, payload: dict | None) -> dict[str, Any]:
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
    if not model:
        return "unknown"
    
    if "/" in model:
        model = model.rsplit("/", 1)[-1]
    if model.startswith("eu.anthropic."):
        name = model.removeprefix("eu.anthropic.")
        if name.startswith("claude-"):
            return name.split("-202", 1)[0]
    
    _KNOWN_ALIASES = frozenset(
        {
            "claude-haiku",
            "claude-sonnet",
            "bedrock-auto",
            "nova-lite",
            "qwen3-32b",
            "qwen3-coder",
        }
    )
    _ALIAS_RULES = {
        "haiku": "claude-haiku",
        "sonnet": "claude-sonnet",
        "nova": "nova-lite",
        "30b-a3b": "qwen3-coder",
        "coder": "qwen3-coder",
        "qwen": "qwen3-coder",
    }
    
    lowered = model.lower()
    if lowered in _KNOWN_ALIASES:
        return model
    for substring, alias in _ALIAS_RULES.items():
        if substring in lowered:
            return alias
    return model


def strip_existing_footer(content: Any) -> Any:
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
    if isinstance(content, str):
        return content + footer
    if isinstance(content, list):
        if not content:
            return [{"type": "text", "text": footer.lstrip()}]
        last = content[-1]
        if isinstance(last, dict) and last.get("type") == "text":
            return [*content[:-1], {**last, "text": str(last.get("text", "")) + footer}]
    return content
