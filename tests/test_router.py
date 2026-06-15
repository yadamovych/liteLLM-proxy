"""Tests for bedrock-auto routing helpers."""

from __future__ import annotations

import pytest
from litellm.router_strategy.complexity_router.config import ComplexityTier

from core._vscode_context import ChatMode
from core.router import extract_routing_intent, select_model


def test_extract_routing_intent_uses_user_query_tag() -> None:
    prompt = "<context>noise</context><userQuery>refactor this function</userQuery>"
    assert extract_routing_intent(prompt) == "refactor this function"


@pytest.mark.parametrize(
    ("chat_mode", "tier", "intent", "expected_model"),
    [
        (ChatMode.PLAN, ComplexityTier.SIMPLE, "hi", "claude-sonnet"),
        (ChatMode.ASK, ComplexityTier.SIMPLE, "hi", "qwen3-coder"),
        (ChatMode.AGENT, ComplexityTier.SIMPLE, "hi", "qwen3-coder"),
        (None, ComplexityTier.MEDIUM, "What are the tradeoffs between using Redis versus in-memory caching for session storage in this service", "claude-haiku"),
        (None, ComplexityTier.COMPLEX, "Design a multi-region failover strategy for the payment processing pipeline including data consistency guarantees and rollback procedures", "claude-sonnet"),
    ],
)
def test_select_model(
    chat_mode: ChatMode | None,
    tier: ComplexityTier,
    intent: str,
    expected_model: str,
) -> None:
    model, _signals = select_model(
        chat_mode=chat_mode,
        tier=tier,
        intent=intent,
        raw_prompt=intent,
    )
    assert model == expected_model
