"""Thin LLM provider abstraction.

Transport only — prompting lives in karenbot/agent/prompts. Implementations:
AnthropicClient (production), ScriptedClient (deterministic, for demos and
tests without an API key).
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    name: str
    model_version: str

    def generate(
        self,
        task: str,
        system_prompt: str,
        user_content: str,
        output_model: type[T],
    ) -> T:
        """Run `task` and return output validated against `output_model`."""
        ...
