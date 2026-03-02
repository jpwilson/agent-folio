import json
import os

import litellm

import config
from sdks.base import AgentResponse, BaseSDK

# Enable Langfuse callback if keys are present
if os.getenv("LANGFUSE_SECRET_KEY"):
    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]


class LiteLLMSDK(BaseSDK):
    """LiteLLM unified SDK adapter — supports 100+ providers via model string.

    Examples:
        model="gpt-4o-mini"           -> OpenAI
        model="claude-3-5-sonnet-20241022" -> Anthropic
        model="ollama/llama3"         -> Local Ollama
        model="groq/llama-3.1-70b"   -> Groq
    """

    async def chat(self, messages, tools, tool_executor, system_prompt, model):
        # Set API keys (read from config module for runtime updates)
        litellm.api_key = config.OPENAI_API_KEY
        if config.ANTHROPIC_API_KEY:
            litellm.anthropic_key = config.ANTHROPIC_API_KEY
        if config.OPENROUTER_API_KEY:
            os.environ["OPENROUTER_API_KEY"] = config.OPENROUTER_API_KEY

        all_tool_calls = []
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        for _step in range(5):
            kwargs = {"model": model, "messages": full_messages}
            if tools:
                kwargs["tools"] = tools

            response = await litellm.acompletion(**kwargs)
            choice = response.choices[0]
            msg = choice.message

            if hasattr(msg, "tool_calls") and msg.tool_calls:
                # Append assistant message
                full_messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in msg.tool_calls
                        ],
                    }
                )

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
                return AgentResponse(text=msg.content or "", tool_calls=all_tool_calls)

        return AgentResponse(
            text=msg.content or "I reached the maximum number of steps.",
            tool_calls=all_tool_calls,
        )
