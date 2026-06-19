"""Tests for Bedrock prompt cache injection."""

from __future__ import annotations

from callbacks.prompt_cache import (
    apply_prompt_cache_to_messages,
    inject_prompt_cache,
    model_supports_prompt_cache,
    split_vscode_user_content,
)


def test_model_supports_prompt_cache_for_claude_only() -> None:
    assert model_supports_prompt_cache("claude-haiku")
    assert model_supports_prompt_cache("bedrock/eu.anthropic.claude-sonnet-4-6")
    assert not model_supports_prompt_cache("qwen3-coder")


def test_split_vscode_user_content() -> None:
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
    split = split_vscode_user_content(blob)
    assert split is not None
    prefix, question = split
    assert question == "What is a mutex?"
    assert "Terminals folder" in prefix
    assert "open_and_recently_viewed_files" in prefix


def test_apply_prompt_cache_splits_last_user_message() -> None:
    blob = (
        "The current date is 2026-06-19. Terminals folder: /home/devops/.cursor/projects/foo/terminals\n"
        "Shell: zsh\n"
        "Workspace Path: /home/devops/projects/private/liteLLM-proxy\n"
        "What is a mutex?"
    )
    messages = [{"role": "user", "content": blob}]
    updated = apply_prompt_cache_to_messages(messages)

    assert updated is not messages
    content = updated[0]["content"]
    assert isinstance(content, list)
    assert len(content) == 2
    assert content[0]["cache_control"] == {"type": "ephemeral"}
    assert "Terminals folder" in content[0]["text"]
    assert content[1]["text"] == "What is a mutex?"
    assert "cache_control" not in content[1]


def test_apply_prompt_cache_marks_second_to_last_user_message() -> None:
    messages = [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
        {"role": "user", "content": "second question"},
    ]
    updated = apply_prompt_cache_to_messages(messages)

    first_user = updated[0]["content"]
    assert isinstance(first_user, list)
    assert first_user[-1]["cache_control"] == {"type": "ephemeral"}


def test_inject_prompt_cache_skips_qwen() -> None:
    kwargs = {
        "model": "qwen3-coder",
        "messages": [{"role": "user", "content": "hello"}],
    }
    assert inject_prompt_cache(kwargs) is kwargs


def test_inject_prompt_cache_updates_claude_request() -> None:
    blob = (
        "The current date is 2026-06-19. Terminals folder: /home/devops/.cursor/projects/foo/terminals\n"
        "Shell: zsh\n"
        "Workspace Path: /home/devops/projects/private/liteLLM-proxy\n"
        "What is a mutex?"
    )
    kwargs = {
        "model": "claude-haiku",
        "messages": [{"role": "user", "content": blob}],
    }
    updated = inject_prompt_cache(kwargs)

    assert updated is not kwargs
    content = updated["messages"][0]["content"]
    assert isinstance(content, list)
    assert content[0]["cache_control"] == {"type": "ephemeral"}
