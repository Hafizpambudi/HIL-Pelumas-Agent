import json

from pelumas_agent.config import get_settings
from pelumas_agent.llm.base import LLMClient, LLMMessage, LLMResponse, ToolCall


class OpenAIClient(LLMClient):
    def __init__(
        self, api_key: str | None = None, model: str | None = None, base_url: str | None = None
    ):
        from openai import OpenAI

        settings = get_settings()
        self.client = OpenAI(
            api_key=api_key or settings.openai_api_key,
            base_url=base_url or settings.openai_base_url or None,
        )
        self.model = model or settings.openai_model

    def complete(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        payload = [{"role": "system", "content": system}]
        for message in messages:
            if message.role == "state":
                payload.append(
                    {"role": "system", "content": f"Conversation state: {message.content}"}
                )
            elif message.role == "tool":
                payload.append(
                    {"role": "user", "content": f"[tool result]\n{message.content}"}
                )
            else:
                payload.append({"role": message.role, "content": message.content})
        kwargs = {}
        if tools:
            kwargs["tools"] = [
                {"type": "function", "function": tool} for tool in tools
            ]
        response = self.client.chat.completions.create(
            model=self.model, messages=payload, **kwargs
        )
        choice = response.choices[0].message
        if choice.tool_calls:
            calls = [
                ToolCall(name=tc.function.name, arguments=json.loads(tc.function.arguments or "{}"))
                for tc in choice.tool_calls
            ]
            return LLMResponse(tool_calls=calls)
        return LLMResponse(text=choice.content or "")
