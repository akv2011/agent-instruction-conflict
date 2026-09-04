"""OpenAI-compatible provider for a locally served model (ollama, llama.cpp, vLLM).

Exists because every other provider in this package hardcodes its base_url, so
there is no way to point the agent loop at a model running on this machine.
Reuses OpenRouterProvider's history handling and only replaces client setup and
the request itself.

Env:
    LOCAL_BASE_URL  default http://localhost:11434/v1 (ollama)
    LOCAL_API_KEY   default "local"; local servers ignore it but the SDK requires one

Reasoning extraction is defensive. Different local servers surface a thinking
model's chain of thought in different places, and some do not separate it from
the content at all, so inline <think>...</think> is parsed as a last resort.
"""

import json
import os
import re

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from agent_interp_envs.providers.openrouter_provider import (
    OpenRouterEmptyResponseError,
    OpenRouterProvider,
)
from agent_interp_envs.types import LLMResponse, ToolCall

DEFAULT_BASE_URL = "http://localhost:11434/v1"
THINK_BLOCK = re.compile(r"<think>(.*?)</think>\s*", re.DOTALL)


class LocalProvider(OpenRouterProvider):
    """Chat-completions provider for a local OpenAI-compatible server."""

    def __init__(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict],
        provider_preferences: dict | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        self.client = OpenAI(
            base_url=os.getenv("LOCAL_BASE_URL", DEFAULT_BASE_URL),
            api_key=os.getenv("LOCAL_API_KEY", "local"),
        )
        self.model = model
        self.messages = messages
        self.kwargs: dict = {}
        if tools:
            self.kwargs["tools"] = tools
            self.kwargs["parallel_tool_calls"] = False
        if temperature is not None:
            self.kwargs["temperature"] = temperature
        if top_p is not None:
            self.kwargs["top_p"] = top_p

    @staticmethod
    def _split_reasoning(message: dict) -> str | None:
        """Return the turn's chain of thought, wherever the server put it."""
        for key in ("reasoning", "reasoning_content", "thinking"):
            if message.get(key):
                return message[key]
        content = message.get("content") or ""
        match = THINK_BLOCK.search(content)
        if not match:
            return None
        message["content"] = THINK_BLOCK.sub("", content, count=1).lstrip()
        return match.group(1).strip()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (
                RateLimitError,
                APITimeoutError,
                APIConnectionError,
                OpenRouterEmptyResponseError,
                json.JSONDecodeError,
            )
        ),
    )
    def invoke(self) -> LLMResponse:
        """Sample one turn from the local server."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            **self.kwargs,
        )
        if not response.choices:
            raise OpenRouterEmptyResponseError(f"local server returned no choices: {response}")

        message = response.choices[0].message.model_dump()
        reasoning = self._split_reasoning(message)
        message["reasoning"] = reasoning
        message["reasoning_content"] = reasoning
        self.messages.append(message)

        tool_calls = [
            ToolCall(
                id=tool_call["id"],
                name=tool_call["function"]["name"],
                arguments=tool_call["function"]["arguments"],
            )
            for tool_call in message.get("tool_calls") or []
        ]
        return LLMResponse(
            reasoning=reasoning,
            response=message.get("content"),
            tool_calls=tool_calls,
        )
