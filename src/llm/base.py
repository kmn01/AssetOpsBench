"""Abstract LLM backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .usage import CompletionUsage


class LLMBackend(ABC):
    """Abstract interface for LLM backends."""

    @abstractmethod
    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        """Generate text given a prompt."""
        ...

    def generate_with_usage(
        self, prompt: str, temperature: float = 0.0
    ) -> tuple[str, CompletionUsage]:
        """Generate text and optional token counts (default: unknown usage).

        Backends that do not report usage return :class:`CompletionUsage()` with
        all-``None`` fields. :class:`LiteLLMBackend` fills fields when the
        provider returns them.
        """
        return self.generate(prompt, temperature), CompletionUsage()
