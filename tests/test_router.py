"""Tests for bedrock-auto keyword routing."""

from __future__ import annotations

import pytest
from litellm.router_strategy.complexity_router.config import ComplexityTier

from core.router import classify_complexity_tier, infer_complexity_tier, normalize_user_text, select_model


def test_normalize_user_text_extracts_user_query() -> None:
    blob = (
        "<reminderInstructions>Recommend step by step and implement changes.</reminderInstructions>"
        "<userQuery>hi</userQuery>"
    )
    assert normalize_user_text(blob) == "hi"


def test_normalize_user_text_extracts_snake_case_user_query() -> None:
    blob = (
        "<rules>Recommend step by step implementation.</rules>"
        "<user_query>What is a mutex?</user_query>"
    )
    assert normalize_user_text(blob) == "What is a mutex?"


def test_classify_mutex_from_cursor_envelope() -> None:
    blob = (
        "<rules>Recommend step by step implementation.</rules>"
        "<user_query>What is a mutex?</user_query>"
    )
    intent = normalize_user_text(blob)
    tier, signals = classify_complexity_tier(intent)
    assert intent == "What is a mutex?"
    assert tier is ComplexityTier.SIMPLE
    assert any("factual" in signal for signal in signals)


def test_normalize_user_text_vscode_plain_context_before_question() -> None:
    blob = (
        "The current date is 2026-06-19. Terminals folder: /home/devops/.cursor/projects/foo/terminals\n"
        "Shell: zsh\n"
        "Workspace Path: /home/devops/projects/private/liteLLM-proxy\n"
        "Note: Prefer absolute paths in tool calls.\n"
        "<open_and_recently_viewed_files>\n"
        "Files that are currently open and visible in the user's IDE:\n"
        "- /home/devops/projects/private/liteLLM-proxy/tests/test_router.py (total lines: 143)\n"
        "</open_and_recently_viewed_files>\n"
        "What is a mutex?"
    )
    intent = normalize_user_text(blob)
    tier, signals = classify_complexity_tier(intent)
    assert intent == "What is a mutex?"
    assert tier is ComplexityTier.SIMPLE
    assert any("factual" in signal for signal in signals)


def test_normalize_user_text_empty_user_query_tail() -> None:
    blob = (
        "<reminderInstructions>Recommend implement debug.</reminderInstructions>"
        "<userQuery></userQuery>\nhello world"
    )
    assert normalize_user_text(blob) == "hello world"


def test_normalize_user_text_ignores_boilerplate_before_test() -> None:
    blob = (
        "You are in agent mode. Recommend implementing tests.\n"
        "<userQuery></userQuery>\n"
        "test"
    )
    assert normalize_user_text(blob) == "test"


def test_normalize_user_text_boilerplate_plain_lines() -> None:
    blob = "You are in agent mode. Recommend implementing tests.\ntest"
    assert normalize_user_text(blob) == "test"


def test_classify_test_routes_simple() -> None:
    tier, signals = classify_complexity_tier("test")
    assert tier is ComplexityTier.SIMPLE
    assert any("greeting" in signal for signal in signals)


def test_normalize_user_text_prefers_longest_line() -> None:
    blob = (
        "<reminderInstructions>Recommend implement debug.</reminderInstructions>\n"
        "Refactor this function to\n"
        "extract a shared validation helper."
    )
    assert normalize_user_text(blob) == "Refactor this function to extract a shared validation helper."


def test_classify_multiline_fragment() -> None:
    tier, signals = classify_complexity_tier("extract a shared validation helper.")
    assert tier is ComplexityTier.MEDIUM
    assert any("coding" in signal or "validation" in signal for signal in signals)


@pytest.mark.parametrize(
    ("intent", "expected_tier", "expected_rule"),
    [
        ("hi", ComplexityTier.SIMPLE, "rule=greeting"),
        ("hello world", ComplexityTier.SIMPLE, "rule=casual-short"),
        ("test message", ComplexityTier.SIMPLE, "rule=casual-short"),
        ("What is a mutex?", ComplexityTier.SIMPLE, "rule=factual"),
        (
            "What are the tradeoffs between Redis and in-memory caching for session storage?",
            ComplexityTier.MEDIUM,
            "rule=medium",
        ),
        (
            "Refactor this function to extract a shared validation helper.",
            ComplexityTier.MEDIUM,
            "rule=coding",
        ),
        (
            "Explain why this test is flaky and suggest a minimal fix.",
            ComplexityTier.MEDIUM,
            "rule=medium",
        ),
        (
            "Design a multi-region failover strategy for the payment processing pipeline.",
            ComplexityTier.COMPLEX,
            "rule=complex",
        ),
        (
            "Tell me more about the history of programming languages over time.",
            ComplexityTier.MEDIUM,
            "rule=default-long",
        ),
        ("thanks", ComplexityTier.SIMPLE, "rule=default-short"),
    ],
)
def test_classify_complexity_tier(
    intent: str,
    expected_tier: ComplexityTier,
    expected_rule: str,
) -> None:
    tier, signals = classify_complexity_tier(intent)
    assert tier is expected_tier
    assert any(expected_rule in signal for signal in signals)


def test_infer_complexity_tier_alias() -> None:
    assert infer_complexity_tier("hi") is ComplexityTier.SIMPLE


@pytest.mark.parametrize(
    ("tier", "expected_model"),
    [
        (ComplexityTier.SIMPLE, "qwen3-coder"),
        (ComplexityTier.MEDIUM, "claude-haiku"),
        (ComplexityTier.COMPLEX, "claude-sonnet"),
    ],
)
def test_select_model(tier: ComplexityTier, expected_model: str) -> None:
    model, signals = select_model(tier=tier)
    assert model == expected_model
    assert any(f"tier={tier.value}" in signal for signal in signals)
