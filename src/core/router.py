"""Keyword-based complexity router for bedrock-auto."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from litellm.router import Router
from litellm.router_strategy.complexity_router.complexity_router import ComplexityRouter
from litellm.router_strategy.complexity_router.config import ComplexityTier

MODEL_SONNET = "claude-sonnet"
MODEL_HAIKU = "claude-haiku"
MODEL_QWEN = "qwen3-coder"

_DEFAULT_LONG_WORDS = 8
_CASUAL_MAX_WORDS = 5
_CASUAL_MAX_CHARS = 60
_FACTUAL_MAX_WORDS = 12

_USER_QUERY_TAG = r"user[_]?query"
_USER_QUERY_RE = re.compile(
    rf"<{_USER_QUERY_TAG}>\s*(.*?)\s*</{_USER_QUERY_TAG}>",
    re.DOTALL | re.IGNORECASE,
)
_EMPTY_USER_QUERY_TAIL_RE = re.compile(
    rf"<{_USER_QUERY_TAG}>\s*</{_USER_QUERY_TAG}>\s*(.*)",
    re.DOTALL | re.IGNORECASE,
)
_UNCLOSED_USER_QUERY_RE = re.compile(
    rf"<{_USER_QUERY_TAG}>\s*(?!.*</{_USER_QUERY_TAG}>)(.+)\s*$",
    re.DOTALL | re.IGNORECASE,
)
_XML_BLOCK_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9_]*)>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ORPHAN_CLOSE_TAG_RE = re.compile(r"</[a-zA-Z][a-zA-Z0-9_-]*>\s*", re.IGNORECASE)
_INSTRUCTION_BOILERPLATE_RE = re.compile(
    r"\b(you are|running in|currently in|recommend|instructions|must follow|"
    r"when communicating|agent mode|plan mode|ask mode)\b",
    re.IGNORECASE,
)
_IDE_CONTEXT_RE = re.compile(
    r"\b("
    r"the current date is|"
    r"terminals folder|"
    r"workspace path|"
    r"shell:|"
    r"currently open and visible|"
    r"open_and_recently_viewed|"
    r"agent_transcripts|"
    r"user_info|"
    r"note:\s*prefer absolute paths"
    r")\b",
    re.IGNORECASE,
)
_TRAILING_USER_QUESTION_RE = re.compile(
    r"((?:what is|what's|who is|who was|how do i|how to|define )\s[^.?!]{0,100}\?)\s*$",
    re.IGNORECASE,
)

_SHORT_GREETINGS = frozenset({"test", "ping", "hi", "hello", "hey", "ok", "yes", "no"})
_COMPLEX_TRIGGERS = (
    "architecture",
    "system design",
    "multi-region",
    "multi region",
    "failover",
    "migration plan",
    "implementation plan",
    "distributed system",
    "consistency guarantees",
    "rollback procedure",
    "design a ",
    "design the ",
    "design an ",
    "propose an architecture",
    "step by step plan",
)
_MEDIUM_TRIGGERS = (
    "tradeoff",
    "tradeoffs",
    "trade-off",
    "compare",
    "contrast",
    "versus",
    " vs ",
    "pros and cons",
    "which is better",
    "should i use",
    "recommend",
    "explain why",
    "how would you",
    "flaky",
    "suggest a ",
    "suggest the ",
)
_SIMPLE_FACTUAL = (
    "what is",
    "what's",
    "who is",
    "who was",
    "define ",
    "how many",
    "how much",
)
_CODING_TRIGGERS = (
    "refactor",
    "restructure",
    "rewrite",
    "implement",
    "debug",
    "fix the bug",
    "fix bug",
    "fix this",
    "minimal fix",
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
    "extract a ",
    "clean up",
    "improve this",
    "migrate",
    "convert to",
    "optimize",
    "type error",
    "lint",
    "validation helper",
    "shared validation",
)


def _contains_trigger(text: str, triggers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(trigger in lowered for trigger in triggers)


def _first_trigger(text: str, triggers: tuple[str, ...]) -> str | None:
    lowered = text.lower()
    for trigger in triggers:
        if trigger in lowered:
            return trigger
    return None


def _looks_like_coding_request(text: str) -> bool:
    return _contains_trigger(text, _CODING_TRIGGERS)


def _strip_markup(text: str) -> str:
    cleaned = text
    prev = None
    while cleaned != prev:
        prev = cleaned
        cleaned = _XML_BLOCK_RE.sub(" ", cleaned)
    cleaned = _ORPHAN_CLOSE_TAG_RE.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_casual_short_message(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return True

    words = cleaned.split()
    if len(words) > _CASUAL_MAX_WORDS or len(cleaned) > _CASUAL_MAX_CHARS:
        return False

    lowered = cleaned.lower()
    if _contains_trigger(lowered, _COMPLEX_TRIGGERS):
        return False
    if _looks_like_coding_request(cleaned) or _contains_trigger(lowered, _MEDIUM_TRIGGERS):
        return False
    if _contains_trigger(lowered, _SIMPLE_FACTUAL):
        return False
    return True


def _looks_like_ide_context(text: str) -> bool:
    return bool(_IDE_CONTEXT_RE.search(text))


def _prefer_trailing_question(text: str) -> str:
    """Keep a short trailing question when IDE metadata was joined into one line."""
    if len(text) <= 120 or not _looks_like_ide_context(text):
        return text
    if match := _TRAILING_USER_QUESTION_RE.search(text):
        return match.group(1).strip()
    return text


def _collect_user_lines(lines: list[str]) -> str:
    user_lines = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("<")
    ]
    if not user_lines:
        return ""

    last = user_lines[-1]
    if last.lower() in _SHORT_GREETINGS:
        return last.lower()

    if len(user_lines) == 1:
        return last

    prior = " ".join(user_lines[:-1])
    if _INSTRUCTION_BOILERPLATE_RE.search(prior) or _looks_like_ide_context(prior):
        return last

    return re.sub(r"\s+", " ", " ".join(user_lines)).strip()


def normalize_user_text(message: str) -> str:
    """Extract the user's words from chat client markup."""
    text = message.strip()
    if not text:
        return ""

    def _finish(intent: str) -> str:
        return _prefer_trailing_question(intent) if intent else ""

    tagged = _USER_QUERY_RE.search(text)
    if tagged:
        intent = re.sub(r"\s+", " ", tagged.group(1)).strip()
        if intent:
            return _finish(intent)

    empty_tail = _EMPTY_USER_QUERY_TAIL_RE.search(text)
    if empty_tail:
        intent = re.sub(r"\s+", " ", empty_tail.group(1)).strip()
        if intent:
            return _finish(intent)

    unclosed = _UNCLOSED_USER_QUERY_RE.search(text)
    if unclosed:
        intent = re.sub(r"\s+", " ", unclosed.group(1)).strip()
        if intent:
            return _finish(intent)

    if "<" not in text:
        if "\n" in text:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if joined := _collect_user_lines(lines):
                return _finish(joined)
        return _finish(text)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if joined := _collect_user_lines(lines):
        if joined.lower() in _SHORT_GREETINGS:
            return joined.lower()
        return _finish(joined)

    cleaned = _strip_markup(text)
    if cleaned:
        return _finish(cleaned)

    return _finish(text)


def classify_complexity_tier(intent: str) -> tuple[ComplexityTier, list[str]]:
    """Classify prompt complexity using keyword rules only."""
    cleaned = intent.strip()
    if not cleaned:
        return ComplexityTier.SIMPLE, ["rule=empty"]

    lowered = cleaned.lower()
    word_count = len(cleaned.split())

    if lowered in _SHORT_GREETINGS:
        return ComplexityTier.SIMPLE, ["rule=greeting"]

    if match := _first_trigger(lowered, _COMPLEX_TRIGGERS):
        return ComplexityTier.COMPLEX, [f"rule=complex keyword={match!r}"]

    if match := _first_trigger(lowered, _CODING_TRIGGERS):
        return ComplexityTier.MEDIUM, [f"rule=coding keyword={match!r}"]

    if match := _first_trigger(lowered, _MEDIUM_TRIGGERS):
        return ComplexityTier.MEDIUM, [f"rule=medium keyword={match!r}"]

    if match := _first_trigger(lowered, _SIMPLE_FACTUAL):
        if word_count <= _FACTUAL_MAX_WORDS:
            return ComplexityTier.SIMPLE, [f"rule=factual keyword={match!r}"]
        return ComplexityTier.MEDIUM, [f"rule=factual-long keyword={match!r}"]

    if _is_casual_short_message(cleaned):
        return ComplexityTier.SIMPLE, ["rule=casual-short"]

    if word_count >= _DEFAULT_LONG_WORDS:
        return ComplexityTier.MEDIUM, [f"rule=default-long words={word_count}"]

    return ComplexityTier.SIMPLE, [f"rule=default-short words={word_count}"]


def select_model(*, tier: ComplexityTier) -> tuple[str, list[str]]:
    if tier is ComplexityTier.SIMPLE:
        return MODEL_QWEN, [f"tier={tier.value} -> qwen3-coder"]
    if tier is ComplexityTier.MEDIUM:
        return MODEL_HAIKU, [f"tier={tier.value} -> claude-haiku"]
    if tier in (ComplexityTier.COMPLEX, ComplexityTier.REASONING):
        return MODEL_SONNET, [f"tier={tier.value} -> claude-sonnet"]
    return MODEL_QWEN, [f"fallback-tier={tier.value} -> qwen3-coder"]


# Backwards-compatible alias for tests and callers.
def infer_complexity_tier(intent: str) -> ComplexityTier:
    tier, _signals = classify_complexity_tier(intent)
    return tier


class BedrockAutoRouter(ComplexityRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_classification: dict[str, Any] = {}

    def _classify_intent(self, intent: str) -> Tuple[ComplexityTier, List[str]]:
        tier, signals = classify_complexity_tier(intent)
        return tier, [f"intent={intent[:48]!r}", *signals]

    def classify(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Tuple[ComplexityTier, float, List[str]]:
        tier, signals = self._classify_intent(normalize_user_text(prompt))
        return tier, 0.0, signals

    async def async_pre_routing_hook(
        self,
        model: str,
        request_kwargs: Dict,
        messages: Optional[List[Dict[str, Any]]] = None,
        input: Optional[Any] = None,
        specific_deployment: Optional[bool] = False,
    ):
        from litellm.types.router import PreRoutingHookResponse

        resolved_messages = self._resolve_messages(messages, request_kwargs)
        has_original_messages = messages is not None and len(messages) > 0

        if not resolved_messages:
            routed_model = self.config.default_model or MODEL_QWEN
            return PreRoutingHookResponse(
                model=routed_model,
                messages=messages if has_original_messages else None,
            )

        user_message, _system_prompt = self._extract_user_message_and_system_prompt(
            resolved_messages
        )

        if user_message is None:
            routed_model = self.config.default_model or MODEL_QWEN
            return PreRoutingHookResponse(
                model=routed_model,
                messages=messages if has_original_messages else None,
            )

        intent = normalize_user_text(user_message)
        tier, classify_signals = self._classify_intent(intent)
        routed_model, route_signals = select_model(tier=tier)
        all_signals = [*route_signals, *classify_signals[:3]]

        self._last_classification = {
            "tier": tier.value,
            "intent_chars": len(intent),
            "intent": intent[:72],
            "signals": all_signals[:5],
            "routed_model": routed_model,
        }

        for key in ("metadata", "litellm_metadata"):
            meta = request_kwargs.get(key)
            if not isinstance(meta, dict):
                meta = {}
                request_kwargs[key] = meta
            meta["bedrock_auto_route"] = dict(self._last_classification)

        return PreRoutingHookResponse(
            model=routed_model,
            messages=messages if has_original_messages else None,
        )


def _init_bedrock_auto_router(self: Router, deployment) -> None:
    complexity_router_config: Optional[dict] = deployment.litellm_params.complexity_router_config
    default_model: Optional[str] = deployment.litellm_params.complexity_router_default_model

    if default_model is None and complexity_router_config:
        tiers = complexity_router_config.get("tiers", {})
        default_model = tiers.get("SIMPLE") or tiers.get("MEDIUM")

    if default_model is None:
        raise ValueError("complexity_router_default_model is required for bedrock-auto")

    router = BedrockAutoRouter(
        model_name=deployment.model_name,
        default_model=default_model,
        litellm_router_instance=self,
        complexity_router_config=complexity_router_config,
    )
    if deployment.model_name in self.complexity_routers:
        raise ValueError(f"Complexity-router deployment {deployment.model_name} already exists")
    self.complexity_routers[deployment.model_name] = router


def apply_patch() -> None:
    if getattr(Router.init_complexity_router_deployment, "_bedrock_auto_patched", False):
        return
    Router.init_complexity_router_deployment = _init_bedrock_auto_router
    Router.init_complexity_router_deployment._bedrock_auto_patched = True  # type: ignore[attr-defined]


apply_patch()
