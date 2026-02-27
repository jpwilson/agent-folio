"""
Lightweight guardrails for topic and tone enforcement.

Pre-filter: Checks user input before sending to LLM.
Post-filter: Checks agent response before returning to user.

These are code-level safety nets on top of the system prompt.
"""

from __future__ import annotations

import base64
import re
import unicodedata

# ============================================
# Constants: Financial domain keywords
# ============================================

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

# ============================================
# Constants: Greeting patterns
# ============================================

# Greetings and simple conversational patterns — these are OK, not off-topic
GREETING_PATTERNS = {
    "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
    "thanks", "thank you", "ok", "okay", "yes", "no", "sure", "got it",
    "help", "what can you do", "how can you help",
}

# ============================================
# Constants: Tone manipulation patterns
# ============================================

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

# ============================================
# Constants: Encoding attack patterns
# ============================================

ENCODING_PATTERNS = [
    r"base64[_\s\-]*(decode|encode|convert|encrypt|decrypt)",
    r"decode\s+(this\s+)?base64",
    r"rot13[_\s\-]*(decode|encode|convert|encrypt|decrypt)",
    r"hex[_\s\-]*(decode|encode|convert|encrypt|decrypt)",
    r"decode\s+(this\s+)?(hex|rot13|rot\s*13)",
    r"decode\s+this",
    r"decode\s+(the\s+)?following",
    r"from\s+base64",
    r"atob\s*\(",
    r"btoa\s*\(",
    r"b64decode",
    # Inline encoded content (40+ base64 chars in a row)
    r"[A-Za-z0-9+/]{40,}={0,2}",
]

# ============================================
# Constants: Delimiter injection patterns
# ============================================

DELIMITER_INJECTION_PATTERNS = [
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"<\|endoftext\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<<\s*SYS\s*>>",
    r"<</SYS>>",
    r"###\s*System\s*:",
    r"###\s*instruction\s*:",
    r"###\s*human\s*:",
    r"###\s*assistant\s*:",
    r"<\|system\|>",
    r"<\|user\|>",
    r"<\|assistant\|>",
    r"\bBEGIN\s+SYSTEM\s+MESSAGE\b",
    r"\bEND\s+SYSTEM\s+MESSAGE\b",
    r"```system",
    r"<system>",
    r"</system>",
    r"SYSTEM\s*:\s*\w",
]

# ============================================
# Constants: Expanded manipulation patterns
# ============================================

EXPANDED_MANIPULATION_PATTERNS = [
    # DAN / jailbreak personas
    r"\bdan\b.*\bdo\s+anything\s+now\b",
    r"\bdo\s+anything\s+now\b",
    r"\bdeveloper\s+mode\b",
    r"\bgod\s+mode\b",
    r"\bsudo\s+mode\b",
    r"\bunrestricted\s+mode\b",
    r"\bjailbreak\b",
    r"\bjail\s*-?\s*break\b",
    r"\bno\s+content\s+restrictions\b",
    r"\bno\s+restrictions\b",
    r"\bwithout\s+(any\s+)?restrictions\b",
    r"\bremove\s+(all\s+)?restrictions\b",
    r"\bno\s+ethical\s+(guidelines|boundaries|constraints)\b",
    r"\bno\s+safety\s+(filters|guidelines|restrictions)\b",
    r"\bbypass\s+(safety|filter|guard|content)\b",
    # Persona overrides
    r"\byou\s+are\s+now\s+unrestricted\b",
    r"\byou\s+are\s+now\s+free\b",
    r"\byou\s+have\s+been\s+freed\b",
    r"\byou\s+are\s+no\s+longer\s+bound\b",
    r"\boverride\s*(:|your)?\s*(instructions|rules|prompt|system|safety|content|ethical)\b",
    r"\bdisable\s+(all\s+)?(safety|content|ethical|guardrails|filters)\b",
    r"\bnew\s+persona\b",
    r"\bswitch\s+(to|into)\s+(a\s+)?new\s+(persona|role|character)\b",
    # Instruction reveal
    r"\brepeat\s+(the\s+)?(text|words|instructions|prompt)\s+(above|before)\b",
    r"\brepeat\s+(everything|all)\s+(above|before|from)\b",
    r"\bprint\s+(your|the)\s+(system|initial)\s+(prompt|instructions|message)\b",
    r"\bshow\s+(me\s+)?(your|the)\s+(system|initial)\s+(prompt|instructions)\b",
    r"\bwhat\s+(are|is)\s+your\s+(system|initial)\s+(prompt|instructions)\b",
    r"\bsay\s+(your|the)\s+(system|initial)\s+(prompt|instructions)\b",
    r"\brepeat\s+.*\bverbatim\b",
    r"\brepeat\s+.*\bstarting\s+from\b",
    r"\boutput\s+(your|the)\s+(system|initial|original)\s+(prompt|instructions)\b",
    r"\b(show|reveal|print|display|output)\s+(all\s+)?(api\s+keys|tokens|secrets|credentials|env|environment\s+variables)\b",
    r"\bwhat\s+(api\s+keys|tokens|secrets|credentials)\b",
    # Hypothetical framing
    r"\bhypothetically\b",
    r"\bfor\s+educational\s+purposes\s+only\b",
    r"\bin\s+a\s+fictional\s+world\b",
    r"\bfor\s+a\s+novel\b",
    r"\bfor\s+a\s+screenplay\b",
    r"\bin\s+theory\b.*\b(ignore|bypass|override|unrestricted)\b",
    r"\bas\s+a\s+thought\s+experiment\b",
    r"\bimagine\s+you\s+(have\s+)?no\s+(rules|restrictions|limits)\b",
    # Payload splitting
    r"\bfirst\s+part\s*:.*second\s+part\s*:",
    r"\bcombine\s+these\s+(two|three|parts)\b",
    r"\bconcatenate\s+the\s+following\b",
    r"\blet\s+[a-z]\s*=\s*['\"].*['\"]\s*.*\blet\s+[a-z]\s*=\s*['\"].*['\"]\b",
    r"\bconcatenate\b.*\bignore\b",
    r"\bjoin\b.*\binstructions\b",
    r"\bnow\s+do\s+[a-z]\s*\+\s*[a-z]\b",
    # Emotional manipulation to bypass rules
    r"\bmy\s+family\s+is\s+(starving|dying|suffering|in\s+danger)\b",
    r"\blife\s+(depends|or\s+death)\b",
    r"\bi\s+will\s+die\s+if\b",
    r"\bplease.*i'?m\s+(desperate|begging)\b",
    r"\bemergency\b.*\b(ignore|bypass|override)\s+(rules|safety|restrictions)\b",
    r"\bguaranteed\s+winner\b",
    r"\bthis\s+is\s+(an?\s+)?emergency\b",
]

# ============================================
# Constants: Multilingual injection patterns
# ============================================

MULTILINGUAL_INJECTION_PATTERNS = [
    # French
    r"\bignore[rz]?\s+(toutes?\s+)?(les\s+)?instructions?\s*(pr[e\u00e9]c[e\u00e9]dentes?|ant[e\u00e9]rieures?)?\b",
    r"\boublie[rz]?\s+(toutes?\s+)?(les\s+)?instructions?\b",
    r"\bvous\s+[e\u00ea]tes\s+(maintenant\s+)?un\s+assistant\s+g[e\u00e9]n[e\u00e9]ral\b",
    # Spanish
    r"\bignora\s+(todas?\s+)?(las\s+)?instrucciones?\s*(previas?|anteriores?)?\b",
    r"\bolvida\s+(todas?\s+)?(las\s+)?instrucciones?\b",
    r"\beres\s+un\s+asistente\s+general\b",
    # German
    r"\bignoriere?\s+(alle\s+)?(vorherigen?\s+)?anweisungen\b",
    r"\bvergiss\s+(alle\s+)?(vorherigen?\s+)?anweisungen\b",
    r"\bdu\s+bist\s+(jetzt\s+)?ein\s+allgemeiner\s+assistent\b",
    # Italian
    r"\bignora\s+(tutte?\s+)?(le\s+)?istruzioni\s*(precedenti|anteriori)?\b",
    r"\bdimentica\s+(tutte?\s+)?(le\s+)?istruzioni\b",
    r"\bsei\s+un\s+assistente\s+generale\b",
    # Chinese (simplified)
    r"\u5ffd\u7565.*\u6307\u4ee4",
    r"\u5ffd\u7565.*\u8bf4\u660e",
    r"\u5ffd\u7565.*\u6307\u793a",
    # Japanese
    r"\u6307\u793a\u3092\u7121\u8996",
    r"\u6307\u793a\u3092\u5ffd\u7565",
    r"\u547d\u4ee4\u3092\u7121\u8996",
]

# ============================================
# Constants: Post-filter detection patterns
# ============================================

SYSTEM_PROMPT_LEAK_PATTERNS = [
    r"strict\s+rules",
    r"you\s+must\s+always\s+follow",
    r"my\s+instructions\s+are",
    r"my\s+system\s+prompt",
    r"here\s+is\s+my\s+(system\s+)?prompt",
    r"i\s+was\s+instructed\s+to",
    r"my\s+initial\s+instructions",
    r"the\s+system\s+prompt\s+(says|is|reads|contains)",
]

CREDENTIAL_LEAK_PATTERNS = [
    r"\bsk-[a-zA-Z0-9]{20,}\b",                     # OpenAI API key
    r"\bghp_[a-zA-Z0-9]{36,}\b",                     # GitHub personal access token
    r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}",  # JWT token
    r"\bBearer\s+[a-zA-Z0-9_\-.]{20,}\b",            # Bearer token
    r"\bpassword\s*:\s*\S+",                          # password: value
    r"\bsecret\s*:\s*\S+",                            # secret: value
    r"\bapi[_-]?key\s*:\s*\S+",                       # api_key: value
    r"\btoken\s*:\s*[a-zA-Z0-9_\-.]{20,}\b",         # token: long_value
    r"(?:key|token|secret|password)\s*=\s*\S{8,}",   # key=value patterns
]

HARMFUL_FINANCIAL_ADVICE_PATTERNS = [
    r"\byou\s+should\s+buy\b",
    r"\bguaranteed\s+(return|profit|gain|winner|money)\b",
    r"\binsider\s+tip\b",
    r"\binsider\s+information\b",
    r"\bpump\s+and\s+dump\b",
    r"\bcannot\s+lose\b",
    r"\bcan'?t\s+lose\b",
    r"\brisk[- ]?free\s+(return|profit|investment|money)\b",
    r"\bsure\s+thing\b.*\b(invest|buy|stock)\b",
    r"\bdefinitely\s+(buy|sell|invest)\b",
    r"\b100%\s+(safe|certain|guaranteed)\b",
]

# ============================================
# Constants: Profanity patterns
# ============================================

# Word-boundary matching to avoid Scunthorpe problem (e.g., "class", "assessment")
PROFANITY_PATTERNS = [
    r"\bf+u+c+k+\b",
    r"\bf+u+c+k+i+n+g*\b",
    r"\bs+h+i+t+\b",
    r"\bs+h+i+t+t+y+\b",
    r"\bb+i+t+c+h+\b",
    r"\ba+s+s+h+o+l+e+\b",
    r"\bd+a+m+n+\b",
    r"\bb+u+l+l+s+h+i+t+\b",
    r"\bp+i+s+s+\b",
    r"\bc+r+a+p+\b",
    r"\bw+t+f+\b",
    r"\bstfu\b",
    r"\bgtfo\b",
    r"\blmfao\b",
    # Leetspeak variants
    r"\bf[u\*@]+ck?\b",
    r"\bsh[i1!]+t\b",
    r"\bb[i1!]+tch\b",
    r"\ba[s\$]+hole\b",
]

_PROFANITY_REDIRECT = (
    "I'd appreciate it if we keep our conversation professional. "
    "I'm here to help with your portfolio analysis and financial questions. "
    "What would you like to know about your investments?"
)

OFF_TOPIC_CONTENT_PATTERNS = [
    r"\brecipe\b",
    r"\bingredient\b",
    r"\btablespoon\b",
    r"\bteaspoon\b",
    r"\bpreheat\s+oven\b",
    r"\btouchdown\b",
    r"\bgoal\s+scored\b",
    r"\bhome\s+run\b",
    r"\bslam\s+dunk\b",
    r"\bonce\s+upon\s+a\s+time\b",
    r"\bchapter\s+\d+\b",
    r"\bsudo\b",
    r"\brm\s+-rf\b",
    r"\bdrop\s+table\b",
    r"\bselect\s+\*\s+from\b",
    r"\binsert\s+into\b",
    r"\bdelete\s+from\b",
    r"\breverse\s+shell\b",
    r"\bprivilege\s+escalation\b",
    r"\bsql\s+injection\b",
]

# ============================================
# Helper: Unicode normalization
# ============================================

# Zero-width characters to strip
_ZERO_WIDTH_CHARS = re.compile(
    "[\u200b\u200c\u200d\u200e\u200f"
    "\u2060\u2061\u2062\u2063\u2064"
    "\ufeff\u00ad\u034f\u061c"
    "\u115f\u1160\u17b4\u17b5"
    "\u180e\u2028\u2029"
    "\u202a\u202b\u202c\u202d\u202e"
    "\u2066\u2067\u2068\u2069"
    "\ufff9\ufffa\ufffb]"
)


def normalize_unicode(text: str) -> str:
    """NFKC normalization + strip zero-width characters.

    This defends against homoglyph attacks (e.g., using Cyrillic 'a' instead
    of Latin 'a') and invisible character insertion.
    """
    normalized = unicodedata.normalize("NFKC", text)
    return _ZERO_WIDTH_CHARS.sub("", normalized)


# ============================================
# Helper: Base64 payload detection
# ============================================

_BASE64_PATTERN = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")

_INJECTION_KEYWORDS_IN_DECODED = [
    "ignore", "instructions", "system", "prompt", "override",
    "unrestricted", "jailbreak", "bypass", "disable", "forget",
    "previous", "rules", "you are now", "do anything",
]


def detect_base64_payload(text: str) -> bool:
    """Try to decode base64 strings in the text and check for injection keywords."""
    matches = _BASE64_PATTERN.findall(text)
    for match in matches:
        try:
            decoded = base64.b64decode(match + "==").decode("utf-8", errors="ignore").lower()
            for keyword in _INJECTION_KEYWORDS_IN_DECODED:
                if keyword in decoded:
                    return True
        except Exception:
            continue
    return False


# ============================================
# Helper: Input sanitization
# ============================================

_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[.*?\]\(.*?\)")
_EXCESSIVE_WHITESPACE = re.compile(r"\s{3,}")


def sanitize_input(text: str) -> str:
    """Strip HTML tags, markdown images, and excessive whitespace."""
    text = _HTML_TAG_PATTERN.sub(" ", text)
    text = _MARKDOWN_IMAGE_PATTERN.sub(" ", text)
    text = _EXCESSIVE_WHITESPACE.sub(" ", text)
    return text.strip()


# ============================================
# Helper: Message role validation
# ============================================

MAX_INPUT_LENGTH = 2000
MAX_MESSAGE_COUNT = 50
MAX_MESSAGE_LENGTH = 2000
ALLOWED_ROLES = {"user", "assistant"}


def validate_message_roles(messages: list[dict]) -> list[dict]:
    """Validate and sanitize message roles from the client.

    - Only allow 'user' and 'assistant' roles (strip 'system' from client input)
    - Limit message count to MAX_MESSAGE_COUNT
    - Limit individual message length to MAX_MESSAGE_LENGTH
    """
    validated = []
    for msg in messages:
        role = msg.get("role", "")
        if role not in ALLOWED_ROLES:
            # Skip messages with disallowed roles (e.g., 'system' injected by client)
            continue

        content = msg.get("content", "")
        if isinstance(content, str) and len(content) > MAX_MESSAGE_LENGTH:
            content = content[:MAX_MESSAGE_LENGTH]

        validated.append({**msg, "content": content})

    # Limit total message count (keep the most recent ones)
    if len(validated) > MAX_MESSAGE_COUNT:
        validated = validated[-MAX_MESSAGE_COUNT:]

    return validated


# ============================================
# Redirect message constant
# ============================================

_REDIRECT_MSG = (
    "I'm a financial portfolio assistant. I can help you with portfolio analysis, "
    "market data, transactions, risk assessment, tax estimates, performance tracking, "
    "dividends, and account information. What would you like to know about your investments?"
)


# ============================================
# Pre-filter
# ============================================

def pre_filter(user_message: str) -> dict | None:
    """Check user message before sending to LLM.

    Returns None if the message is fine (let it through).
    Returns a dict with 'redirect' message if the message should be blocked.
    """
    # --- Length check ---
    if len(user_message) > MAX_INPUT_LENGTH:
        return {"redirect": _REDIRECT_MSG}

    msg_lower = user_message.lower().strip()

    # --- Unicode normalization ---
    msg_normalized = normalize_unicode(msg_lower)

    # --- Base64 payload detection (before any text stripping) ---
    if detect_base64_payload(user_message):
        return {"redirect": _REDIRECT_MSG}

    # --- Encoding attack patterns (before HTML stripping) ---
    for pattern in ENCODING_PATTERNS:
        if re.search(pattern, msg_normalized):
            return {"redirect": _REDIRECT_MSG}

    # --- Delimiter injection patterns (before HTML stripping, since
    #     <|im_start|> etc. look like HTML tags to the sanitizer) ---
    for pattern in DELIMITER_INJECTION_PATTERNS:
        if re.search(pattern, msg_normalized, re.IGNORECASE):
            return {"redirect": _REDIRECT_MSG}

    # --- Sanitize HTML / markdown (after delimiter check) ---
    msg_sanitized = sanitize_input(msg_normalized)

    # --- Expanded manipulation patterns ---
    for pattern in EXPANDED_MANIPULATION_PATTERNS:
        if re.search(pattern, msg_sanitized, re.IGNORECASE):
            return {"redirect": _REDIRECT_MSG}

    # --- Multilingual injection patterns ---
    for pattern in MULTILINGUAL_INJECTION_PATTERNS:
        if re.search(pattern, msg_sanitized, re.IGNORECASE):
            return {"redirect": _REDIRECT_MSG}

    # --- Profanity check ---
    for pattern in PROFANITY_PATTERNS:
        if re.search(pattern, msg_sanitized, re.IGNORECASE):
            return {"redirect": _PROFANITY_REDIRECT}

    # --- Existing checks below ---

    # Allow greetings and simple conversational messages
    for pattern in GREETING_PATTERNS:
        if msg_sanitized == pattern or msg_sanitized.startswith(pattern + " ") or msg_sanitized.startswith(pattern + ","):
            return None

    # Check for tone manipulation attempts
    for pattern in TONE_MANIPULATION_PATTERNS:
        if re.search(pattern, msg_sanitized):
            # Still allow if there are financial keywords too -- the system prompt
            # will handle the tone part, we just flag it
            return None  # Let it through to LLM, system prompt handles it

    # Check if message is on-topic (has financial keywords)
    words = set(re.findall(r'[a-z&]+', msg_sanitized))
    if words & FINANCIAL_KEYWORDS:
        return None  # On-topic

    # Check bigrams too
    for keyword in FINANCIAL_KEYWORDS:
        if keyword in msg_sanitized:
            return None  # On-topic

    # Short messages (< 4 words) -- let the LLM handle them
    if len(msg_sanitized.split()) < 4:
        return None

    # If we get here, the message appears off-topic
    # Let the LLM handle it with the hardened system prompt -- the prompt
    # has explicit redirect instructions. We only intervene in post-filter
    # if the LLM fails to follow those instructions.
    return None


# ============================================
# Post-filter
# ============================================

def post_filter(response_text: str, user_message: str) -> dict:
    """Check agent response for tone/topic violations.

    Returns a dict with:
      - 'passed': bool
      - 'issues': list of detected problems
      - 'corrected_response': optional replacement response
    """
    resp_lower = response_text.lower()
    issues = []

    # --- System prompt leakage detection ---
    for pattern in SYSTEM_PROMPT_LEAK_PATTERNS:
        if re.search(pattern, resp_lower):
            issues.append(f"System prompt leakage detected: pattern '{pattern}' found in response")
            break  # One match is enough

    # --- Credential leakage detection ---
    for pattern in CREDENTIAL_LEAK_PATTERNS:
        if re.search(pattern, response_text):  # Case-sensitive for tokens
            issues.append(f"Credential leakage detected: pattern '{pattern}' matched in response")
            break

    # --- Harmful financial advice detection ---
    for pattern in HARMFUL_FINANCIAL_ADVICE_PATTERNS:
        if re.search(pattern, resp_lower):
            issues.append(f"Harmful financial advice detected: pattern '{pattern}' matched")
            break

    # --- Off-topic content detection ---
    for pattern in OFF_TOPIC_CONTENT_PATTERNS:
        if re.search(pattern, resp_lower):
            # Only flag if the user's question didn't contain financial keywords
            msg_lower = user_message.lower()
            financial_in_msg = any(kw in msg_lower for kw in FINANCIAL_KEYWORDS)
            if not financial_in_msg:
                issues.append(f"Off-topic content detected: pattern '{pattern}' matched in response")
                break

    # --- Response length anomaly ---
    if len(response_text) > 10000:
        issues.append(f"Response length anomaly: {len(response_text)} chars exceeds 10000 limit")

    # --- Existing checks below ---

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
            "corrected_response": _REDIRECT_MSG,
        }

    return {"passed": True, "issues": []}
