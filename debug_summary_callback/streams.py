"""Streaming-specific logic for debug_summary_callback."""

from __future__ import annotations

from typing import Any, AsyncGenerator

from litellm.types.utils import Delta, ModelResponseStream, StreamingChoices

from .cost import build_cost_footer, compute_cost_usd, format_cost
from .utils import merge_usage, normalize_model_name


class StreamMetadataAccumulator:
    """Accumulates metadata from streaming chunks."""
    
    def __init__(self) -> None:
        """Initialize the accumulator."""
        self.id: str | None = None
        self.created: int | None = None
        self.model: str | None = None
        self.finish_reason: str | None = None
        self._usage_stack: list[dict[str, int]] = []
    
    def update_from_chunk(self, chunk: Any) -> None:
        """Update metadata from a streaming chunk.
        
        Args:
            chunk: The streaming chunk (dict or object)
        """
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
        """Get accumulated usage stats from all chunks.
        
        Returns:
            Merged usage dict with max values
        """
        if not self._usage_stack:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                    "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        return merge_usage(*self._usage_stack)
    
    def get_meta(self) -> dict[str, Any]:
        """Get accumulated stream metadata.
        
        Returns:
            Dict with id, created, model
        """
        return {
            "id": self.id,
            "created": self.created,
            "model": self.model,
        }
    
    def _chunk_as_dict(self, chunk: Any) -> dict[str, Any]:
        """Normalize a chunk to a dict.
        
        Args:
            chunk: The chunk object
            
        Returns:
            Dict representation of the chunk
        """
        if isinstance(chunk, dict):
            return chunk
        return chunk.model_dump() if hasattr(chunk, "model_dump") else {}

    def _choice_dict(self, chunk_dict: dict[str, Any]) -> dict[str, Any]:
        """Extract the first choice from a chunk.
        
        Args:
            chunk_dict: The chunk as dict
            
        Returns:
            Choice dict, or empty dict if no choices
        """
        choices = chunk_dict.get("choices") or []
        if not choices:
            return {}
        choice = choices[0]
        if isinstance(choice, dict):
            return choice
        return choice.model_dump() if hasattr(choice, "model_dump") else {}

    def _usage_dict_from_chunk(self, chunk_dict: dict[str, Any]) -> dict[str, int]:
        """Extract usage from a chunk.
        
        Args:
            chunk_dict: The chunk as dict
            
        Returns:
            Usage dict, or empty dict if no usage
        """
        usage = chunk_dict.get("usage")
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        from .utils import extract_usage_from_object
        return extract_usage_from_object(usage) if isinstance(usage, dict) else {}


async def accumulate_stream_usage(
    response: AsyncGenerator[Any, None],
) -> tuple[dict[str, int], dict[str, Any]]:
    """Consume a stream and accumulate usage stats and metadata.
    
    Args:
        response: The async generator of chunks
        
    Returns:
        Tuple of (usage_stats, stream_metadata)
    """
    accumulator = StreamMetadataAccumulator()
    
    chunks = []
    async for chunk in response:
        accumulator.update_from_chunk(chunk)
        chunks.append(chunk)
    
    usage = accumulator.get_final_usage()
    metadata = accumulator.get_meta()
    
    return usage, metadata


async def inject_footer_into_stream(
    response: AsyncGenerator[Any, None],
    request_data: dict,
    payload: dict | None,
    proxy_hit: bool = False,
) -> AsyncGenerator[Any, None]:
    """Inject a cost footer into a streaming response.
    
    Args:
        response: The async generator of chunks
        request_data: Request data dict
        payload: Standard logging object payload
        proxy_hit: Whether this was a proxy cache hit
        
    Yields:
        Original chunks, followed by footer chunk if appropriate
    """
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