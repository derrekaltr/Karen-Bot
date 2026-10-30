"""Anthropic Claude client: structured outputs via messages.parse().

Current-generation models (Sonnet 5.5 and newer) removed forced tool_choice;
the supported way to get schema-validated output is structured outputs —
`client.messages.parse(output_format=<pydantic model>)`, which returns a
validated instance on `response.parsed_output`.
"""

from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from karenbot.config import get_settings

T = TypeVar("T", bound=BaseModel)

# Cheap-classification tasks run on the smaller model.
CLASSIFIER_TASKS = {"interpret_reply"}


class AnthropicClient:
    name = "anthropic"

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self._client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._agent_model = settings.agent_model
        self._classifier_model = settings.classifier_model
        self.model_version = self._agent_model

    def generate(
        self,
        task: str,
        system_prompt: str,
        user_content: str,
        output_model: type[T],
    ) -> T:
        model = self._classifier_model if task in CLASSIFIER_TASKS else self._agent_model
        response = self._client.messages.parse(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            output_format=output_model,
        )
        if response.parsed_output is None:
            raise RuntimeError(f"model returned no parsable output for task {task}")
        return response.parsed_output

    def generate_with_search(
        self,
        task: str,
        system_prompt: str,
        user_content: str,
        output_model: type[T],
        max_searches: int = 12,
    ) -> T:
        """Structured output with the server-side web_search tool enabled.

        Server tools run on Anthropic's side; a turn can pause mid-search
        (stop_reason "pause_turn"), in which case the partial content is
        echoed back to continue the same turn.
        """
        messages: list[Any] = [{"role": "user", "content": user_content}]
        tools: list[Any] = [
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": max_searches,
            }
        ]
        for _ in range(4):  # initial request + up to 3 pause_turn continuations
            response = self._client.messages.parse(
                model=self._agent_model,
                max_tokens=16000,
                system=system_prompt,
                messages=messages,
                tools=tools,
                output_format=output_model,
            )
            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue
            if response.parsed_output is None:
                raise RuntimeError(f"model returned no parsable output for task {task}")
            return response.parsed_output
        raise RuntimeError(f"task {task} did not complete after repeated pause_turn")
