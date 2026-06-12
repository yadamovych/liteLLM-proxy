"""Shared VS Code / Copilot text handling for bedrock_auto_router and debug_summary_callback."""

from __future__ import annotations

import re

_COPILOT_MARKERS = ("<context>", "<editorContext>", "<attachments>", "<toolResults>")

_VSCODE_BLOCK_TAGS = (
    "context",
    "editorContext",
    "attachments",
    "toolResults",
    "userQuery",
    "codeSelection",
    "promptReferences",
    "reminderInstructions",
)

_STRIP_RE = re.compile(
    r"<(" + "|".join(_VSCODE_BLOCK_TAGS) + r")>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
_TRAILING_TAG_RE = re.compile(
    r"<(" + "|".join(_VSCODE_BLOCK_TAGS) + r")>.*",
    re.DOTALL | re.IGNORECASE,
)
_USER_QUERY_RE = re.compile(r"<userQuery>\s*(.*?)\s*</userQuery>", re.DOTALL | re.IGNORECASE)
_CODE_SELECTION_RE = re.compile(
    r"<codeSelection[^>]*>(.*?)</codeSelection>",
    re.DOTALL | re.IGNORECASE,
)
_DATE_LINE_RE = re.compile(r"the current date is [^.]+\.?", re.IGNORECASE)
_FILE_LINE_RE = re.compile(r"the user'?s current file is [^.]+\.?", re.IGNORECASE)
_PATH_RE = re.compile(
    r"(?:/|\\)[\w./\\-]+\.(?:yaml|yml|py|ts|tsx|js|json|md|sh|go|rs)\b",
    re.IGNORECASE,
)


def is_copilot_payload(text: str) -> bool:
    """Return True when text contains VS Code/Copilot XML markers."""
    if not text:
        return False
    lowered = text.lstrip().lower()
    return any(m.lower() in lowered for m in _COPILOT_MARKERS)


def strip_vscode_wrapper(text: str | None) -> str:
    """Remove VS Code XML wrapper blocks from prompt text."""
    if not text:
        return ""
    cleaned = _STRIP_RE.sub(" ", text)
    cleaned = _TRAILING_TAG_RE.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_routing_intent(text: str | None) -> str:
    """Extract user intent — never score Copilot XML or system-style boilerplate."""
    if not text:
        return ""

    tagged = _USER_QUERY_RE.search(text)
    if tagged:
        return re.sub(r"\s+", " ", tagged.group(1)).strip()

    cleaned = strip_vscode_wrapper(text)
    cleaned = _DATE_LINE_RE.sub(" ", cleaned)
    cleaned = _FILE_LINE_RE.sub(" ", cleaned)
    cleaned = _PATH_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return ""

    if "\n" in text or "\n" in cleaned:
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if lines:
            cleaned = lines[-1]

    return cleaned.strip()


def has_vscode_code_context(raw_prompt: str) -> bool:
    """Non-empty editor selection or fenced code in the user query → needs Sonnet.

    VS Code sends <editorContext> with activeEditor/filePath on every message;
    that metadata alone must NOT force Sonnet.
    """
    if not raw_prompt:
        return False

    for match in _CODE_SELECTION_RE.finditer(raw_prompt):
        if match.group(1).strip():
            return True

    user_query = _USER_QUERY_RE.search(raw_prompt)
    if user_query and "```" in user_query.group(1):
        return True

    return False
