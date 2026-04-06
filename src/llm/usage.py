"""Token usage from LLM completions (LiteLLM / OpenAI-style usage objects)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompletionUsage:
    """Input/output token counts for one completion call.

    ``None`` means the provider or client did not report that value.
    """

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    @staticmethod
    def from_litellm_usage(usage: Any | None) -> CompletionUsage:
        """Best-effort parse of ``litellm.completion`` response ``usage``."""
        if usage is None:
            return CompletionUsage()
        pt = getattr(usage, "prompt_tokens", None)
        ct = getattr(usage, "completion_tokens", None)
        tt = getattr(usage, "total_tokens", None)
        return CompletionUsage(
            prompt_tokens=int(pt) if pt is not None else None,
            completion_tokens=int(ct) if ct is not None else None,
            total_tokens=int(tt) if tt is not None else None,
        )

    def __add__(self, other: CompletionUsage) -> CompletionUsage:
        prompt = _add_optional_int(self.prompt_tokens, other.prompt_tokens)
        completion = _add_optional_int(
            self.completion_tokens, other.completion_tokens
        )
        if prompt is not None and completion is not None:
            total = prompt + completion
        else:
            total = _add_optional_int(self.total_tokens, other.total_tokens)
        return CompletionUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
        )

    def to_json_fields(self) -> dict[str, int | None]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


def _add_optional_int(a: int | None, b: int | None) -> int | None:
    if a is None and b is None:
        return None
    return (a or 0) + (b or 0)


def sum_usage_optional(usages: list[CompletionUsage]) -> CompletionUsage:
    """Fold a list; missing components stay missing unless at least one addend had a value."""
    acc = CompletionUsage()
    for u in usages:
        acc = acc + u
    return acc
