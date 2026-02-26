import json
from anthropic import AsyncAnthropic
from sdks.base import BaseSDK, AgentResponse
from config import ANTHROPIC_API_KEY


def _convert_tools_to_anthropic(tools: list[dict]) -> list[dict]:
    """Convert OpenAI tool format to Anthropic tool format."""
    result = []
    for t in tools:
        fn = t.get("function", {})
        result.append(
            {
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return result


def _convert_messages_to_anthropic(messages: list[dict]) -> list[dict]:
    """Convert OpenAI message format to Anthropic format (no system in messages)."""
    result = []
    for m in messages:
        if m["role"] == "system":
            continue
        result.append({"role": m["role"], "content": m.get("content", "")})
    return result


class AnthropicSDK(BaseSDK):
    """Native Anthropic Python SDK adapter."""

    async def chat(self, messages, tools, tool_executor, system_prompt, model):
        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        all_tool_calls = []
        anthropic_tools = _convert_tools_to_anthropic(tools) if tools else []
        conv_messages = _convert_messages_to_anthropic(messages)

        for _step in range(5):
            kwargs = {
                "model": model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": conv_messages,
            }
            if anthropic_tools:
                kwargs["tools"] = anthropic_tools

            response = await client.messages.create(**kwargs)

            # Check for tool use in response
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if tool_use_blocks:
                # Build assistant message content
                assistant_content = []
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            }
                        )

                conv_messages.append({"role": "assistant", "content": assistant_content})

                # Execute tools and build tool result message
                tool_results = []
                for block in tool_use_blocks:
                    all_tool_calls.append({"tool": block.name, "args": block.input})
                    result = await tool_executor(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )

                conv_messages.append({"role": "user", "content": tool_results})
            else:
                # Final text response
                text = ""
                for block in response.content:
                    if block.type == "text":
                        text += block.text
                return AgentResponse(text=text, tool_calls=all_tool_calls)

        # Max steps reached
        return AgentResponse(
            text="I reached the maximum number of steps.",
            tool_calls=all_tool_calls,
        )
