import json
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from sdks.base import BaseSDK, AgentResponse
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY


def _get_langchain_model(model: str):
    """Create the appropriate LangChain chat model based on model string."""
    if model.startswith("claude"):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, api_key=ANTHROPIC_API_KEY, max_tokens=4096)
    else:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, api_key=OPENAI_API_KEY)


class LangChainSDK(BaseSDK):
    """LangChain SDK adapter using tool-calling agent pattern."""

    async def chat(self, messages, tools, tool_executor, system_prompt, model):
        llm = _get_langchain_model(model)
        all_tool_calls = []

        # Convert OpenAI tool definitions to LangChain StructuredTools
        # We wrap them for definition only; actual execution goes through tool_executor
        langchain_tools = []
        for t in tools:
            fn = t.get("function", {})
            name = fn.get("name", "")
            desc = fn.get("description", "")
            params = fn.get("parameters", {})

            # Create a dummy tool for binding to the model
            def _make_fn(tool_name):
                async def _fn(**kwargs):
                    return await tool_executor(tool_name, kwargs)
                _fn.__name__ = tool_name
                return _fn

            st = StructuredTool.from_function(
                coroutine=_make_fn(name),
                name=name,
                description=desc,
                args_schema=None,
            )
            langchain_tools.append(st)

        # Bind tools to model
        llm_with_tools = llm.bind_tools(langchain_tools) if langchain_tools else llm

        # Convert messages to LangChain format
        lc_messages = [SystemMessage(content=system_prompt)]
        for m in messages:
            if m["role"] == "user":
                lc_messages.append(HumanMessage(content=m.get("content", "")))
            elif m["role"] == "assistant":
                lc_messages.append(AIMessage(content=m.get("content", "")))

        for _step in range(5):
            response = await llm_with_tools.ainvoke(lc_messages)

            if response.tool_calls:
                lc_messages.append(response)

                for tc in response.tool_calls:
                    fn_name = tc["name"]
                    fn_args = tc.get("args", {})
                    all_tool_calls.append({"tool": fn_name, "args": fn_args})

                    result = await tool_executor(fn_name, fn_args)
                    lc_messages.append(
                        ToolMessage(content=json.dumps(result), tool_call_id=tc["id"])
                    )
            else:
                return AgentResponse(
                    text=response.content or "", tool_calls=all_tool_calls
                )

        return AgentResponse(
            text="I reached the maximum number of steps.",
            tool_calls=all_tool_calls,
        )
