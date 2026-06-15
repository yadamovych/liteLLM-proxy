"""Shared VS Code / Cursor detection logic."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

_COPILOT_MARKERS = ("<context>", "<editorContext>", "<attachments>", "<toolResults>")
_COPILOT_PATTERN = re.compile(r"|".join(re.escape(m) for m in _COPILOT_MARKERS), re.IGNORECASE)

_MODE_RE = re.compile(
    r'(?:running in|currently in|switched to)\s+["\']?(?P<mode>plan|agent|ask)["\']?\s+mode',
    re.IGNORECASE,
)
_PLANNING_HINT_RE = re.compile(
    r"\bplanning mode\b|\bgenerate an implementation plan\b|\bdo not make (?:any )?code edits\b",
    re.IGNORECASE,
)
_AGENT_HINT_RE = re.compile(
    r"\bautomated coding agent\b|<toolResults>|tool_search_tool|run_in_terminal",
    re.IGNORECASE,
)
_ASK_HINT_RE = re.compile(
    r'\bask mode\b|when the user is requesting a code sample, you can answer it directly',
    re.IGNORECASE,
)


class ChatMode(str, Enum):
    PLAN = "plan"
    AGENT = "agent"
    ASK = "ask"


def is_copilot_payload(text: str) -> bool:
    if not text:
        return False
    lowered = text.lstrip().lower()
    return any(m.lower() in lowered for m in _COPILOT_MARKERS)


def has_vscode_code_context(text: str) -> bool:
    if not text:
        return False
    return bool(_COPILOT_PATTERN.search(text))


def strip_copilot_markers(text: str) -> str:
    if not text or not is_copilot_payload(text):
        return text
    result = text
    for marker in _COPILOT_MARKERS:
        result = result.replace(marker, "")
    return result.strip()


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
        return " ".join(parts)
    return ""


def detect_chat_mode(text: str) -> ChatMode | None:
    if not text:
        return None

    match = _MODE_RE.search(text)
    if match:
        return ChatMode(match.group("mode").lower())

    if _PLANNING_HINT_RE.search(text):
        return ChatMode.PLAN
    if _ASK_HINT_RE.search(text):
        return ChatMode.ASK
    if _AGENT_HINT_RE.search(text):
        return ChatMode.AGENT
    return None


def detect_chat_mode_from_messages(messages: list[dict[str, Any]]) -> ChatMode | None:
    parts: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        text = _message_text(msg.get("content"))
        if text:
            parts.append(text)
    if not parts:
        return None
    return detect_chat_mode("\n".join(parts))


def detect_chat_mode_from_metadata(metadata: dict[str, Any] | None) -> ChatMode | None:
    if not metadata:
        return None
    for key in ("chat_mode", "mode", "agent_mode"):
        raw = metadata.get(key)
        if isinstance(raw, str):
            lowered = raw.lower().strip()
            if lowered in {m.value for m in ChatMode}:
                return ChatMode(lowered)
    return None
