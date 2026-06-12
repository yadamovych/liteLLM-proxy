"""Shared VS Code detection logic.

This is a private module (leading underscore) that provides
VS Code/Copilot detection utilities shared across modules.
"""

from __future__ import annotations

import re

_COPILOT_MARKERS = ("<context>", "<editorContext>", "<attachments>", "<toolResults>")
_COPILOT_PATTERN = re.compile(r"|".join(re.escape(m) for m in _COPILOT_MARKERS), re.IGNORECASE)


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
