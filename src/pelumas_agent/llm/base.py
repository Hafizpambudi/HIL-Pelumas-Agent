from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class ToolCall:
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient:
    def complete(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        raise NotImplementedError
