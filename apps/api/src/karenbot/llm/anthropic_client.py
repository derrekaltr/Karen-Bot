"""Anthropic Claude client: structured output via forced tool use."""

from typing import TypeVar

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
        tool_name = f"emit_{task}_result"
        response = self._client.messages.create(
            model=model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            tools=[
                {
                    "name": tool_name,
                    "description": f"Return the structured result for task '{task}'.",
                    "input_schema": output_model.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
        )
        for block in response.content:
            if block.type == "tool_use":
                return output_model.model_validate(block.input)
        raise RuntimeError(f"model returned no tool_use block for task {task}")
