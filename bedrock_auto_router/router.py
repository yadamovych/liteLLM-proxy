"""BedrockAutoRouter — VS Code-aware complexity router."""

from __future__ import annotations

from typing import Any

from litellm.router_strategy.complexity_router.complexity_router import ComplexityRouter
from litellm.router_strategy.complexity_router.config import ComplexityTier

from .intent import (
    is_plain_short_intent,
    is_short_greeting,
    needs_capable_model,
    resolve_intent,
    upgrade_tier_for_coding,
)


class BedrockAutoRouter(ComplexityRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_classification: dict[str, Any] = {}

    def classify(
        self, prompt: str, system_prompt: str | None = None
    ) -> tuple[ComplexityTier, float, list[str]]:
        intent = resolve_intent(prompt)

        lowered = intent.lower().strip()
        is_plain_short = is_short_greeting(intent) or is_plain_short_intent(intent)
        if is_plain_short:
            tier, score, signals = (
                ComplexityTier.SIMPLE,
                0.0,
                [f"plain-intent ({len(intent)} chars)"],
            )
        else:
            # Score user intent only — system prompt contains coding keywords and
            # would otherwise force COMPLEX for every VS Code chat.
            tier, score, signals = super().classify(intent, None)
            signals = [f"intent={intent[:48]!r}", *signals]

        # A single keyword like "refactor" scores ~0.12 (SIMPLE) with default
        # weights — too low for Sonnet unless we upgrade coding work explicitly.
        # Plain short chat ("test message") must not upgrade just because VS Code
        # attached editor metadata to the payload.
        if not is_plain_short and needs_capable_model(intent, prompt):
            upgraded = upgrade_tier_for_coding(tier)
            if upgraded != tier:
                signals = ["coding-route -> COMPLEX", *signals]
                tier = upgraded

        self._last_classification = {
            "tier": tier.value,
            "score": round(score, 3),
            "stripped_chars": len(intent),
            "intent": intent[:72],
            "signals": signals[:4],
        }
        return tier, score, signals

    async def async_pre_routing_hook(
        self,
        model: str,
        request_kwargs: dict,
        messages: list[dict[str, Any]] | None = None,
        input: Any = None,
        specific_deployment: bool | None = False,
    ):
        response = await super().async_pre_routing_hook(
            model=model,
            request_kwargs=request_kwargs,
            messages=messages,
            input=input,
            specific_deployment=specific_deployment,
        )
        if response is None or not self._last_classification:
            return response

        route_info = {**self._last_classification, "routed_model": response.model}
        for key in ("metadata", "litellm_metadata"):
            meta = request_kwargs.get(key)
            if not isinstance(meta, dict):
                meta = {}
                request_kwargs[key] = meta
            meta["bedrock_auto_route"] = route_info
        return response
