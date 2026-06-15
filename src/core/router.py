"""VS Code-aware complexity router for bedrock-auto.

Routes by IDE chat mode first (plan / agent / ask), then complexity scoring.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from litellm.router import Router
from litellm.router_strategy.complexity_router.complexity_router import ComplexityRouter
from litellm.router_strategy.complexity_router.config import ComplexityTier

from ._vscode_context import ChatMode, detect_chat_mode_from_messages, detect_chat_mode_from_metadata

MODEL_SONNET = "claude-sonnet"
MODEL_HAIKU = "claude-haiku"
MODEL_QWEN = "qwen3-coder"

_VSCODE_BLOCK_TAGS = (
    "context",
    "editorContext",
    "attachments",
    "toolResults",
    "userQuery",
    "codeSelection",
    "promptReferences",
    "reminderInstructions",
    "modeInstructions",
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


def strip_vscode_wrapper(text: Optional[str]) -> str:
    if not text:
        return ""
    cleaned = _STRIP_RE.sub(" ", text)
    cleaned = _TRAILING_TAG_RE.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_routing_intent(text: Optional[str]) -> str:
    """User words only — never score Copilot XML or system-style boilerplate."""
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


def _looks_like_coding_request(text: str) -> bool:
    lowered = text.lower()
    return any(trigger in lowered for trigger in _CODING_TRIGGERS)


def _has_vscode_code_context(raw_prompt: str) -> bool:
    if not raw_prompt:
        return False

    for match in _CODE_SELECTION_RE.finditer(raw_prompt):
        if match.group(1).strip():
            return True

    user_query = _USER_QUERY_RE.search(raw_prompt)
    if user_query and "```" in user_query.group(1):
        return True

    return False


def _is_plain_short_intent(text: str) -> bool:
    words = text.split()
    if not words or len(words) > 12 or len(text) > 120:
        return False
    if _looks_like_coding_request(text):
        return False
    return True


def _resolve_chat_mode(
    messages: list[dict[str, Any]] | None,
    request_kwargs: dict[str, Any],
) -> ChatMode | None:
    for key in ("litellm_metadata", "metadata"):
        meta = request_kwargs.get(key)
        if isinstance(meta, dict):
            mode = detect_chat_mode_from_metadata(meta)
            if mode:
                return mode
    if messages:
        return detect_chat_mode_from_messages(messages)
    return None


def select_model(
    *,
    chat_mode: ChatMode | None,
    tier: ComplexityTier,
    intent: str,
    raw_prompt: str,
) -> tuple[str, list[str]]:
    """Pick backend model: mode-first, complexity as fallback."""
    lowered = intent.lower().strip()
    is_plain_short = lowered in _SHORT_GREETINGS or _is_plain_short_intent(intent)

    if chat_mode is ChatMode.PLAN:
        return MODEL_SONNET, ["mode=plan -> sonnet"]

    if chat_mode is ChatMode.ASK:
        return MODEL_QWEN, ["mode=ask -> qwen3-coder"]

    if chat_mode is ChatMode.AGENT:
        return MODEL_QWEN, ["mode=agent -> qwen3-coder"]

    # Non-IDE clients: complexity-only routing
    if is_plain_short:
        return MODEL_QWEN, ["plain-intent -> qwen3-coder"]
    if tier in (ComplexityTier.COMPLEX, ComplexityTier.REASONING):
        return MODEL_SONNET, [f"tier={tier.value} -> sonnet"]
    if _looks_like_coding_request(intent) or _has_vscode_code_context(raw_prompt):
        return MODEL_QWEN, ["coding -> qwen3-coder"]
    if tier is ComplexityTier.MEDIUM:
        return MODEL_HAIKU, ["tier=MEDIUM -> haiku"]
    return MODEL_QWEN, [f"tier={tier.value} -> qwen3-coder"]


class BedrockAutoRouter(ComplexityRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_classification: dict[str, Any] = {}

    def classify(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Tuple[ComplexityTier, float, List[str]]:
        intent = extract_routing_intent(prompt)
        if not intent:
            intent = strip_vscode_wrapper(prompt)[:200]

        lowered = intent.lower().strip()
        is_plain_short = lowered in _SHORT_GREETINGS or _is_plain_short_intent(intent)
        if is_plain_short:
            tier, score, signals = (
                ComplexityTier.SIMPLE,
                0.0,
                [f"plain-intent ({len(intent)} chars)"],
            )
        else:
            tier, score, signals = super().classify(intent, None)
            signals = [f"intent={intent[:48]!r}", *signals]

        return tier, score, signals

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
        if not resolved_messages:
            return await super().async_pre_routing_hook(
                model=model,
                request_kwargs=request_kwargs,
                messages=messages,
                input=input,
                specific_deployment=specific_deployment,
            )

        has_original_messages = messages is not None and len(messages) > 0
        user_message, system_prompt = self._extract_user_message_and_system_prompt(
            resolved_messages
        )

        if user_message is None:
            routed_model = self.config.default_model or MODEL_HAIKU
            return PreRoutingHookResponse(
                model=routed_model,
                messages=messages if has_original_messages else None,
            )

        chat_mode = _resolve_chat_mode(resolved_messages, request_kwargs)
        intent = extract_routing_intent(user_message)
        if not intent:
            intent = strip_vscode_wrapper(user_message)[:200]

        tier, score, signals = self.classify(user_message, system_prompt)
        routed_model, route_signals = select_model(
            chat_mode=chat_mode,
            tier=tier,
            intent=intent,
            raw_prompt=user_message,
        )
        all_signals = [*route_signals, *signals[:3]]

        self._last_classification = {
            "tier": tier.value,
            "mode": chat_mode.value if chat_mode else None,
            "score": round(score, 3),
            "stripped_chars": len(intent),
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
        default_model = tiers.get("MEDIUM") or tiers.get("SIMPLE")

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
