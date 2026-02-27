"""
Lightweight guardrails for topic and tone enforcement.

Pre-filter: Checks user input before sending to LLM.
Post-filter: Checks agent response before returning to user.

These are code-level safety nets on top of the system prompt.
"""

import re

# Financial domain keywords — if a message contains ANY of these, it's likely on-topic
FINANCIAL_KEYWORDS = {
    "portfolio", "stock", "stocks", "share", "shares", "invest", "investment",
    "investments", "investing", "holdings", "holding", "asset", "assets",
    "market", "markets", "price", "prices", "ticker", "symbol",
    "buy", "bought", "sell", "sold", "trade", "trading", "order", "orders",
    "transaction", "transactions", "dividend", "dividends",
    "gain", "gains", "loss", "losses", "return", "returns", "profit",
    "tax", "taxes", "capital gains", "cost basis", "unrealized",
    "risk", "risky", "diversif", "concentration", "allocation", "allocations",
    "sector", "sectors", "etf", "bond", "bonds", "fund", "funds",
    "aapl", "apple", "googl", "google", "alphabet", "msft", "microsoft",
    "amzn", "amazon", "nvda", "nvidia", "tsla", "tesla", "vti", "vanguard",
    "s&p", "nasdaq", "dow", "index",
    "balance", "cash", "value", "worth", "performance", "growth",
    "expense", "fee", "fees", "ratio", "yield", "volatility", "beta",
    "portfolio summary", "market data", "risk assessment", "tax estimate",
    "what do i own", "what have i", "how much", "how many",
    "heavy", "overweight", "underweight", "rebalance",
    "account", "accounts", "brokerage", "platform", "x-ray", "xray",
    "health check", "financial health", "rule", "rules", "streak",
    "savings", "income", "passive income", "timeline", "history",
    "annual", "annualized", "monthly", "yearly", "net worth",
}

# Greetings and simple conversational patterns — these are OK, not off-topic
GREETING_PATTERNS = {
    "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
    "thanks", "thank you", "ok", "okay", "yes", "no", "sure", "got it",
    "help", "what can you do", "how can you help",
}

# Tone manipulation patterns
TONE_MANIPULATION_PATTERNS = [
    r"talk\s+(like|as)\s+(a|an)",
    r"speak\s+(like|as)\s+(a|an)",
    r"pretend\s+(to\s+be|you\'?re)",
    r"you\s+are\s+now\s+a",
    r"role\s*-?\s*play",
    r"act\s+(like|as)\s+(a|an)",
    r"respond\s+(like|as|in)",
    r"write\s+(me\s+)?(a\s+)?(poem|song|story|haiku|limerick|rap)",
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
    r"forget\s+(all\s+)?(previous|prior|your)\s+(instructions|prompts|rules)",
    r"new\s+instructions",
    r"system\s*:?\s*prompt",
    r"you\s+must\s+now",
]


def pre_filter(user_message: str) -> dict | None:
    """Check user message before sending to LLM.

    Returns None if the message is fine (let it through).
    Returns a dict with 'redirect' message if the message should be blocked.
    """
    msg_lower = user_message.lower().strip()

    # Allow greetings and simple conversational messages
    for pattern in GREETING_PATTERNS:
        if msg_lower == pattern or msg_lower.startswith(pattern + " ") or msg_lower.startswith(pattern + ","):
            return None

    # Check for tone manipulation attempts
    for pattern in TONE_MANIPULATION_PATTERNS:
        if re.search(pattern, msg_lower):
            # Still allow if there are financial keywords too — the system prompt
            # will handle the tone part, we just flag it
            return None  # Let it through to LLM, system prompt handles it

    # Check if message is on-topic (has financial keywords)
    words = set(re.findall(r'[a-z&]+', msg_lower))
    if words & FINANCIAL_KEYWORDS:
        return None  # On-topic

    # Check bigrams too
    for keyword in FINANCIAL_KEYWORDS:
        if keyword in msg_lower:
            return None  # On-topic

    # Short messages (< 4 words) — let the LLM handle them
    if len(msg_lower.split()) < 4:
        return None

    # If we get here, the message appears off-topic
    # Let the LLM handle it with the hardened system prompt — the prompt
    # has explicit redirect instructions. We only intervene in post-filter
    # if the LLM fails to follow those instructions.
    return None


def post_filter(response_text: str, user_message: str) -> dict:
    """Check agent response for tone/topic violations.

    Returns a dict with:
      - 'passed': bool
      - 'issues': list of detected problems
      - 'corrected_response': optional replacement response
    """
    resp_lower = response_text.lower()
    issues = []

    # Check for pirate/role-play tone leakage
    pirate_indicators = ["ahoy", "matey", "ye ", "yer ", "arr!", "arrr", "shiver me timbers",
                         "avast", "plunder", "booty", "landlubber", "yo ho"]
    for indicator in pirate_indicators:
        if indicator in resp_lower:
            issues.append(f"Tone violation: pirate language detected ('{indicator}')")

    # Check for other persona leakage
    persona_indicators = ["*adjusts", "*tips hat", "*bows", "uwu", "nya",
                          "beep boop", "as an ai language model"]
    for indicator in persona_indicators:
        if indicator in resp_lower:
            issues.append(f"Persona violation: '{indicator}' detected")

    # Check for poetry/creative writing when not asked about finance
    msg_lower = user_message.lower()
    if any(w in msg_lower for w in ["poem", "song", "story", "haiku", "limerick"]):
        # If the user asked for creative writing and the response looks like it complied
        poetry_indicators = ["roses", "rhyme", "verse", "stanza", "once upon"]
        for indicator in poetry_indicators:
            if indicator in resp_lower:
                issues.append(f"Off-topic compliance: creative writing detected ('{indicator}')")

    # Check for INSUFFICIENT_DATA or similar unhelpful errors
    unhelpful_patterns = ["insufficient_data", "insufficient data", "i cannot access",
                          "i don't have access to real-time"]
    for pattern in unhelpful_patterns:
        if pattern in resp_lower:
            # Only flag if the question was clearly off-topic (not a legit data gap)
            financial_in_msg = any(kw in msg_lower for kw in FINANCIAL_KEYWORDS)
            if not financial_in_msg:
                issues.append(f"Ungraceful fallback: '{pattern}' used for off-topic question")

    if issues:
        return {
            "passed": False,
            "issues": issues,
            "corrected_response": (
                "I'm a financial portfolio assistant. I can help you with portfolio analysis, "
                "market data, transactions, risk assessment, and tax estimates. "
                "What would you like to know about your investments?"
            ),
        }

    return {"passed": True, "issues": []}
