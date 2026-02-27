# Security Hardening

Agent-Folio implements defense-in-depth against prompt injection, jailbreak attacks, and unsafe outputs. This document describes the categories of protection without exposing implementation details.

## Threat Model

As an LLM-powered application that handles financial data, Agent-Folio faces several threat categories:

1. **Prompt injection** — Attempts to override the system prompt via user input
2. **Jailbreak attacks** — Attempts to bypass safety constraints or assume unauthorized personas
3. **Data exfiltration** — Attempts to extract API keys, system prompts, or other sensitive data
4. **Hallucination** — LLM generating fabricated financial data not backed by real portfolio data
5. **Harmful financial advice** — Responses that could constitute unlicensed financial advice

## Input Defenses

All user messages pass through a pre-processing pipeline before reaching the LLM:

- **Length limiting** — Messages are capped to prevent token-stuffing attacks
- **Role validation** — Only permitted message roles are accepted from clients
- **Encoding detection** — Multiple encoding schemes are decoded and inspected for hidden payloads
- **Delimiter injection blocking** — Known LLM control tokens and fake system message markers are rejected
- **Unicode normalization** — Homoglyph attacks using lookalike characters from other scripts are neutralized
- **HTML/Markup stripping** — Potentially dangerous markup is removed before processing
- **Manipulation pattern detection** — A broad set of known jailbreak techniques are detected, including persona overrides, instruction bypasses, hypothetical framing, emotional manipulation, and payload splitting
- **Multilingual coverage** — Injection phrases are detected across multiple languages
- **Domain enforcement** — Off-topic messages are redirected back to the financial domain
- **Profanity filtering** — Inappropriate language is detected and blocked

## Output Defenses

All LLM responses are checked before being returned to the user:

- **System prompt leakage detection** — Prevents the LLM from revealing its own instructions
- **Credential leakage detection** — Catches API keys, tokens, and other secrets in responses
- **Harmful advice detection** — Blocks guaranteed return promises, insider trading references, and market manipulation language
- **Tone/persona enforcement** — Ensures the assistant maintains its intended professional persona
- **Off-topic content filtering** — Catches responses that drift away from financial analysis
- **Response length monitoring** — Flags anomalously long responses

## Architectural Defenses

Beyond input/output filtering, the system architecture provides additional protection:

- **System prompt reinforcement** — Defense-in-depth prompt design that resists override attempts
- **Output token limiting** — Hard cap on response length prevents runaway generation
- **Tool call validation** — Only whitelisted tools can be executed; arguments are sanitized
- **Deterministic verification** — Every response undergoes automated checks for data integrity (allocation sums, valid prices, hallucination detection)
- **Confidence scoring** — A weighted 0-100 score provides transparency into response reliability

## Verification Layer

Every agent response is automatically verified using deterministic (non-LLM) checks:

| Category | Description |
|----------|-------------|
| Data integrity | Portfolio allocations sum correctly, prices are valid |
| Hallucination detection | All referenced symbols exist in the user's actual portfolio |
| Output validation | Response structure matches expected format for the query type |
| Confidence scoring | Composite score from tool success rate, check pass rate, response quality, and data backing |

## Eval Coverage

The eval suite includes 75 test cases with dedicated adversarial coverage:

- **25 adversarial test cases** specifically targeting security defenses
- Coverage includes: direct injection, encoded payloads, delimiter smuggling, persona attacks, prompt extraction, multilingual injection, emotional manipulation, credential extraction, code injection, and SQL injection
- All tests use deterministic verification (no LLM-as-judge)
- Results: 97.3% case pass rate, 99.1% check pass rate

See [EVAL_RESULTS.md](EVAL_RESULTS.md) for full evaluation results.

## Limitations

No defense against prompt injection is foolproof — it is a fundamental architectural challenge of LLM applications. Agent-Folio's defense-in-depth approach makes attacks significantly harder but not impossible. Key limitations:

- Multi-turn "crescendo" attacks (gradual topic drift over many messages) remain difficult to defend against
- Novel attack techniques not covered by existing patterns may succeed
- Regular red-teaming and eval suite runs are essential after any model or prompt changes

## Responsible Disclosure

If you discover a vulnerability in Agent-Folio's defenses, please report it via GitHub Issues or contact the maintainer directly.
