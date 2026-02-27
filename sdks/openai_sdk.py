import json

from openai import AsyncOpenAI

from config import OPENAI_API_KEY
from sdks.base import AgentResponse, BaseSDK


class OpenAISDK(BaseSDK):
    """Native OpenAI Python SDK adapter."""

    async def chat(self, messages, tools, tool_executor, system_prompt, model):
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        all_tool_calls = []

        # Build messages with system prompt
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        for _step in range(5):  # max 5 tool-calling steps
            response = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                tools=tools if tools else None,
            )

            choice = response.choices[0]
            msg = choice.message

            if msg.tool_calls:
                # Append assistant message with tool calls
                full_messages.append(msg.model_dump())

                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments or "{}")
                    all_tool_calls.append({"tool": fn_name, "args": fn_args})

                    result = await tool_executor(fn_name, fn_args)
                    full_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result),
                        }
                    )
            else:
                # No more tool calls — final response
                return AgentResponse(text=msg.content or "", tool_calls=all_tool_calls)

        # If we hit max steps, return whatever we have
        return AgentResponse(
            text=msg.content or "I reached the maximum number of steps.",
            tool_calls=all_tool_calls,
        )
