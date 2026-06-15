"""Tests for callback utilities."""

from __future__ import annotations

import pytest

from callbacks.utils import normalize_model_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("claude-haiku", "claude-haiku"),
        ("claude-haiku-4.5", "claude-haiku"),
        ("claude-sonnet-4.6", "claude-sonnet"),
        ("bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0", "claude-haiku"),
        ("bedrock/eu.anthropic.claude-sonnet-4-6", "claude-sonnet"),
        ("qwen3-coder", "qwen3-coder"),
        ("bedrock/qwen.qwen3-coder-30b-a3b-v1:0", "qwen3-coder"),
    ],
)
def test_normalize_model_name(raw: str, expected: str) -> None:
    assert normalize_model_name(raw) == expected
