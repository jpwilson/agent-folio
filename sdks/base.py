from abc import ABC, abstractmethod


class AgentResponse:
    def __init__(self, text: str, tool_calls: list[dict]):
        self.text = text
        self.tool_calls = tool_calls


class BaseSDK(ABC):
    """Abstract base class for SDK adapters.

    Each adapter wraps a different LLM SDK and implements a common
    chat interface with tool calling support.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_executor,
        system_prompt: str,
        model: str,
    ) -> AgentResponse:
        """Run a multi-step agent conversation.

        Args:
            messages: Conversation history in OpenAI format
            tools: Tool definitions in OpenAI function-calling format
            tool_executor: async callable(tool_name, args) -> result dict
            system_prompt: System prompt text
            model: Model identifier (e.g. "gpt-4o-mini")

        Returns:
            AgentResponse with final text and list of tool calls made
        """
        ...
