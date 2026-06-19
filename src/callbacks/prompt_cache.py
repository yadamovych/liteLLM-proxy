"""Bedrock prompt cache injection for Claude models."""

from __future__ import annotations

import copy
import os
from typing import Any

from core.router import normalize_user_text

from .utils import message_text, normalize_model_name

CACHE_CONTROL: dict[str, str] = {"type": "ephemeral"}
_MIN_SYSTEM_CACHE_CHARS = 1024
_MIN_VSCODE_PREFIX_CHARS = 200
_IDE_CONTEXT_MARKERS = (
    "the current date is",
    "terminals folder",
    "workspace path",
    "open_and_recently_viewed",
    "currently open and visible",
    "agent_transcripts",
    "user_info",
)
_PROMPT_CACHE_MODELS = frozenset({"claude-haiku", "claude-sonnet"})


def _looks_like_ide_context(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _IDE_CONTEXT_MARKERS)


def prompt_cache_enabled() -> bool:
    return os.environ.get("LITELLM_PROMPT_CACHE", "1").lower() in {"1", "true", "yes", "on"}


def model_supports_prompt_cache(model: str | None) -> bool:
    if not model:
        return False
    return normalize_model_name(model) in _PROMPT_CACHE_MODELS


def messages_have_cache_control(messages: list[dict[str, Any]]) -> bool:
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, dict) and content.get("cache_control"):
            return True
        if isinstance(content, list):
            if any(isinstance(block, dict) and block.get("cache_control") for block in content):
                return True
        if msg.get("cache_control"):
            return True
    return False


def split_vscode_user_content(text: str) -> tuple[str, str] | None:
    """Split a stable IDE envelope prefix from the user's actual words."""
    question = normalize_user_text(text)
    stripped = text.strip()
    if not question or question == stripped:
        return None

    idx = stripped.rfind(question)
    if idx <= 0:
        return None

    prefix = stripped[:idx].strip()
    if len(prefix) < _MIN_VSCODE_PREFIX_CHARS and not _looks_like_ide_context(prefix):
        return None
    return prefix, question


def _content_has_cache_control(content: Any) -> bool:
    if isinstance(content, dict):
        return bool(content.get("cache_control"))
    if isinstance(content, list):
        return any(isinstance(block, dict) and block.get("cache_control") for block in content)
    return False


def _add_cache_to_last_block(content: list[Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for item in content:
        if isinstance(item, dict):
            blocks.append(dict(item))
        else:
            blocks.append({"type": "text", "text": str(item)})
    if not blocks:
        return blocks
    last = blocks[-1]
    if last.get("cache_control"):
        return blocks
    last["cache_control"] = dict(CACHE_CONTROL)
    blocks[-1] = last
    return blocks


def _cache_string_content(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": text, "cache_control": dict(CACHE_CONTROL)}]


def _prepare_cached_message(msg: dict[str, Any], *, min_chars: int = 0) -> dict[str, Any]:
    if _content_has_cache_control(msg.get("content")):
        return msg

    content = msg.get("content")
    if isinstance(content, str):
        if len(content) < min_chars:
            return msg
        return {**msg, "content": _cache_string_content(content)}

    if isinstance(content, list) and content:
        text = message_text(content)
        if len(text) < min_chars:
            return msg
        return {**msg, "content": _add_cache_to_last_block(content)}

    return msg


def apply_prompt_cache_to_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy of messages with Bedrock cache checkpoints added."""
    if not messages:
        return messages

    out = copy.deepcopy(messages)
    changed = False

    for index, msg in enumerate(out):
        if msg.get("role") != "system":
            continue
        cached = _prepare_cached_message(msg, min_chars=_MIN_SYSTEM_CACHE_CHARS)
        if cached is not msg:
            out[index] = cached
            changed = True
        break

    user_indices = [index for index, msg in enumerate(out) if msg.get("role") == "user"]
    if not user_indices:
        return out if changed else messages

    last_index = user_indices[-1]
    last_msg = out[last_index]
    last_content = last_msg.get("content")
    if isinstance(last_content, str) and not _content_has_cache_control(last_content):
        split = split_vscode_user_content(last_content)
        if split:
            prefix, question = split
            out[last_index] = {
                **last_msg,
                "content": [
                    {"type": "text", "text": prefix, "cache_control": dict(CACHE_CONTROL)},
                    {"type": "text", "text": question},
                ],
            }
            changed = True

    user_indices = [index for index, msg in enumerate(out) if msg.get("role") == "user"]
    if len(user_indices) >= 2:
        prev_index = user_indices[-2]
        cached = _prepare_cached_message(out[prev_index])
        if cached is not out[prev_index]:
            out[prev_index] = cached
            changed = True

    return out if changed else messages


def inject_prompt_cache(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Add prompt cache markers to a LiteLLM request when appropriate."""
    if not prompt_cache_enabled():
        return kwargs

    model = str(kwargs.get("model") or kwargs.get("model_name") or "")
    if not model_supports_prompt_cache(model):
        return kwargs

    messages = kwargs.get("messages")
    if not isinstance(messages, list) or not messages:
        return kwargs

    if messages_have_cache_control(messages):
        return kwargs

    new_messages = apply_prompt_cache_to_messages(messages)
    if new_messages is messages:
        return kwargs

    return {**kwargs, "messages": new_messages}
