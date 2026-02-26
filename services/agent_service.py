import json
import os
import uuid
from datetime import datetime

from services.ghostfolio_client import GhostfolioClient
from services.sdk_registry import get_sdk, get_current_model, load_settings
from services.verification import verify_response
from tools import ALL_TOOLS, TOOL_DEFINITIONS

CONVERSATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "conversations")

SYSTEM_PROMPT = """You are a helpful financial assistant for Ghostfolio, a portfolio management app.
You help users understand their investments by analyzing their portfolio, looking up market data, and reviewing their transaction history.
Always be factual and precise with numbers. If you don't have enough data to answer, say so.
When discussing financial topics, include appropriate caveats that this is not financial advice.
When presenting numerical data, always include the currency (e.g., USD).
If you detect any inconsistencies in the data, flag them clearly to the user."""


def _get_conv_path(conversation_id: str) -> str:
    return os.path.join(CONVERSATIONS_DIR, f"{conversation_id}.json")


def _load_conversation(conversation_id: str) -> dict | None:
    path = _get_conv_path(conversation_id)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _save_conversation(conversation: dict):
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)
    path = _get_conv_path(conversation["id"])
    with open(path, "w") as f:
        json.dump(conversation, f, indent=2)


# --- Conversation CRUD ---

def list_conversations(user_id: str) -> dict:
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)
    conversations = []
    for fname in os.listdir(CONVERSATIONS_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(CONVERSATIONS_DIR, fname)
        try:
            with open(path) as f:
                conv = json.load(f)
            if conv.get("userId") == user_id:
                conversations.append(
                    {
                        "id": conv["id"],
                        "title": conv.get("title", "Untitled"),
                        "createdAt": conv.get("createdAt"),
                        "updatedAt": conv.get("updatedAt"),
                        "_count": {"messages": len(conv.get("messages", []))},
                    }
                )
        except Exception:
            continue

    conversations.sort(key=lambda c: c.get("updatedAt", ""), reverse=True)
    return {"conversations": conversations}


def get_conversation(conversation_id: str, user_id: str) -> dict:
    conv = _load_conversation(conversation_id)
    if not conv or conv.get("userId") != user_id:
        return {"error": "Conversation not found"}

    return {
        "conversation": {
            "id": conv["id"],
            "title": conv.get("title"),
            "messages": [
                {
                    "id": m.get("id", ""),
                    "role": m["role"],
                    "content": m["content"],
                    "toolCalls": m.get("toolCalls"),
                    "createdAt": m.get("createdAt"),
                }
                for m in conv.get("messages", [])
            ],
        }
    }


def delete_conversation(conversation_id: str, user_id: str) -> dict:
    conv = _load_conversation(conversation_id)
    if conv and conv.get("userId") == user_id:
        path = _get_conv_path(conversation_id)
        os.remove(path)
    return {"success": True}


# --- Chat ---

async def chat(messages: list[dict], user_id: str, token: str, conversation_id: str | None = None) -> dict:
    client = GhostfolioClient(token)

    # Create or load conversation
    conv_id = conversation_id
    if not conv_id:
        conv_id = str(uuid.uuid4())
        first_user_msg = next((m for m in messages if m["role"] == "user"), None)
        title = (
            first_user_msg["content"][:100]
            if first_user_msg and isinstance(first_user_msg.get("content"), str)
            else "New conversation"
        )
        conv = {
            "id": conv_id,
            "userId": user_id,
            "title": title,
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
            "messages": [],
        }
    else:
        conv = _load_conversation(conv_id)
        if not conv:
            conv = {
                "id": conv_id,
                "userId": user_id,
                "title": "Conversation",
                "createdAt": datetime.utcnow().isoformat(),
                "updatedAt": datetime.utcnow().isoformat(),
                "messages": [],
            }

    # Save the latest user message
    last_msg = messages[-1] if messages else None
    if last_msg and last_msg.get("role") == "user":
        conv["messages"].append(
            {
                "id": str(uuid.uuid4()),
                "role": "user",
                "content": last_msg["content"] if isinstance(last_msg.get("content"), str) else json.dumps(last_msg["content"]),
                "createdAt": datetime.utcnow().isoformat(),
            }
        )

    # Collect tool results for verification
    tool_results = []

    async def tool_executor(tool_name: str, args: dict) -> dict:
        tool_module = ALL_TOOLS.get(tool_name)
        if not tool_module:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        result = await tool_module.execute(client, args)
        tool_results.append({"tool": tool_name, "result": result})
        return result

    # Get SDK and model from settings
    settings = load_settings()
    sdk = get_sdk(settings.get("sdk"))
    model = settings.get("model", get_current_model())

    # Run the agent
    response = await sdk.chat(
        messages=messages,
        tools=TOOL_DEFINITIONS,
        tool_executor=tool_executor,
        system_prompt=SYSTEM_PROMPT,
        model=model,
    )

    # Run verification
    verification = verify_response(tool_results, response.text)

    # Save assistant response
    conv["messages"].append(
        {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": response.text,
            "toolCalls": response.tool_calls if response.tool_calls else None,
            "createdAt": datetime.utcnow().isoformat(),
        }
    )
    conv["updatedAt"] = datetime.utcnow().isoformat()
    _save_conversation(conv)

    return {
        "conversationId": conv_id,
        "message": response.text,
        "toolCalls": response.tool_calls,
        "verification": verification,
    }
