"""Streaming helpers for LiteLLM proxy callbacks."""

from __future__ import annotations

from typing import Any

from litellm.types.utils import Delta, ModelResponseStream, StreamingChoices

from .cost import build_cost_footer, compute_cost_usd, format_cost
from .utils import merge_usage, normalize_model_name


class StreamMetadataAccumulator:
    def __init__(self) -> None:
        self.id: str | None = None
        self.created: int | None = None
        self.model: str | None = None
        self.finish_reason: str | None = None
        self._usage_stack: list[dict[str, int]] = []
    
    def update_from_chunk(self, chunk: Any) -> None:
        chunk_dict = self._chunk_as_dict(chunk)
        
        if chunk_dict.get("id"):
            self.id = chunk_dict["id"]
        if chunk_dict.get("model"):
            self.model = chunk_dict["model"]
        if chunk_dict.get("created"):
            self.created = chunk_dict["created"]
        
        choice = self._choice_dict(chunk_dict)
        if choice.get("finish_reason"):
            self.finish_reason = str(choice["finish_reason"])
        
        usage = self._usage_dict_from_chunk(chunk_dict)
        if usage:
            self._usage_stack.append(usage)
    
    def get_final_usage(self) -> dict[str, int]:
        if not self._usage_stack:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                    "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        return merge_usage(*self._usage_stack)
    
    def get_meta(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created": self.created,
            "model": self.model,
        }
    
    def _chunk_as_dict(self, chunk: Any) -> dict[str, Any]:
        if isinstance(chunk, dict):
            return chunk
        return chunk.model_dump() if hasattr(chunk, "model_dump") else {}

    def _choice_dict(self, chunk_dict: dict[str, Any]) -> dict[str, Any]:
        choices = chunk_dict.get("choices") or []
        if not choices:
            return {}
        choice = choices[0]
        if isinstance(choice, dict):
            return choice
        return choice.model_dump() if hasattr(choice, "model_dump") else {}

    def _usage_dict_from_chunk(self, chunk_dict: dict[str, Any]) -> dict[str, int]:
        usage = chunk_dict.get("usage")
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        from .utils import extract_usage_from_object
        return extract_usage_from_object(usage) if isinstance(usage, dict) else {}


async def accumulate_stream_usage(
    response: Any,
) -> tuple[dict[str, int], dict[str, Any]]:
    accumulator = StreamMetadataAccumulator()
    
    chunks = []
    async for chunk in response:
        accumulator.update_from_chunk(chunk)
        chunks.append(chunk)
    
    usage = accumulator.get_final_usage()
    metadata = accumulator.get_meta()
    
    return usage, metadata


async def inject_footer_into_stream(
    response: Any,
    request_data: dict,
    payload: dict | None,
    proxy_hit: bool = False,
) -> Any:
    accumulator = StreamMetadataAccumulator()
    
    async for chunk in response:
        accumulator.update_from_chunk(chunk)
        yield chunk
    
    usage = accumulator.get_final_usage()
    if not usage.get("prompt_tokens") and not usage.get("completion_tokens"):
        return
    
    metadata = accumulator.get_meta()
    if not metadata.get("model"):
        return
    
    footer = build_cost_footer(
        usage=usage,
        model_name=normalize_model_name(metadata["model"]),
        cost_usd=compute_cost_usd(
            usage=usage,
            request_data=request_data,
            kwargs=request_data,
            payload=payload,
            proxy_hit=proxy_hit,
        ),
        proxy_hit=proxy_hit,
    )
    
    yield ModelResponseStream(
        id=metadata.get("id"),
        created=metadata.get("created"),
        model=metadata.get("model"),
        choices=[StreamingChoices(index=0, delta=Delta(content=footer))],
    )
