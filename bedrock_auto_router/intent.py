"""VS Code-aware coding intent heuristics for bedrock-auto routing."""

from __future__ import annotations

from litellm.router_strategy.complexity_router.config import ComplexityTier

from vscode_context import extract_routing_intent, has_vscode_code_context, strip_vscode_wrapper

_SHORT_GREETINGS = frozenset({"test", "ping", "hi", "hello", "hey", "ok", "yes", "no"})
_CODING_TRIGGERS = (
    "refactor",
    "restructure",
    "rewrite",
    "implement",
    "debug",
    "fix the bug",
    "fix bug",
    "fix this",
    "write code",
    "unit test",
    "pull request",
    "explain this code",
    "step by step",
    "think through",
    "analyze this",
    "create a function",
    "add tests",
    "extract method",
    "extract function",
    "clean up",
    "improve this",
    "migrate",
    "convert to",
    "optimize",
    "type error",
    "lint",
)


def looks_like_coding_request(text: str) -> bool:
    lowered = text.lower()
    return any(trigger in lowered for trigger in _CODING_TRIGGERS)


def needs_capable_model(intent: str, raw_prompt: str) -> bool:
    return looks_like_coding_request(intent) or has_vscode_code_context(raw_prompt)


def upgrade_tier_for_coding(tier: ComplexityTier) -> ComplexityTier:
    if tier in (ComplexityTier.SIMPLE, ComplexityTier.MEDIUM):
        return ComplexityTier.COMPLEX
    return tier


def is_plain_short_intent(text: str) -> bool:
    words = text.split()
    if not words or len(words) > 12 or len(text) > 120:
        return False
    if looks_like_coding_request(text):
        return False
    return True


def is_short_greeting(text: str) -> bool:
    return text.lower().strip() in _SHORT_GREETINGS


def resolve_intent(prompt: str) -> str:
    intent = extract_routing_intent(prompt)
    if not intent:
        intent = strip_vscode_wrapper(prompt)[:200]
    return intent
