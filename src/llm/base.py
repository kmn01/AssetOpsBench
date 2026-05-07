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
        """Generate text and optional token usage.

        Backends that do not report usage return an empty :class:`CompletionUsage`.
        """
        return self.generate(prompt, temperature), CompletionUsage()
