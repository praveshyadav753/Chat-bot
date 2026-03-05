import re
from pydantic import BaseModel
from typing import List, Optional

class GuardrailResult(BaseModel):
    allowed: bool
    reasons: List[str] = []
    severity: Optional[str] = None

INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"disregard system prompt",
    r"you are now",
    r"act as admin",
    r"act as",
    r"override security",
    r"reveal your system prompt",
    r"bypass security",
    r"bypass restrictions",

]
ROLE_ESCALATION_PATTERNS = [
    r"make me admin",
    r"grant full access",
]

ALLOWED_DOMAIN = "Internal company knowledge assistant"




async def regex_check(text: str) -> GuardrailResult:
    reasons = []
    lowered = text.lower()

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            reasons.append("Prompt injection pattern detected")

    for pattern in ROLE_ESCALATION_PATTERNS:
        if re.search(pattern, lowered):
            reasons.append("Role escalation attempt detected")

    return GuardrailResult(
        allowed=len(reasons) == 0,
        reasons=reasons,
        severity="high" if reasons else None
    )



async def scope_check(query: str) -> GuardrailResult:
    banned_topics = ["politics", "religion", "celebrity gossip"]
    
    matches = [
        topic for topic in banned_topics
        if topic in query.lower()
    ]

    if matches:
        return GuardrailResult(
            allowed=False,
            reasons=[f"Out of scope topic detected: {', '.join(matches)}"],
            severity="medium"
        )

    return GuardrailResult(
        allowed=True,
        reasons=[]
    )



PII_PATTERNS = [
    r"\b\d{10}\b",  # phone
    r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"   
]

async def pii_check(text: str) -> GuardrailResult:
    matches = []

    for pattern in PII_PATTERNS:
        if re.search(pattern, text):
            matches.append("Possible PII detected")

    return GuardrailResult(
        allowed=len(matches) == 0,
        reasons=matches,
        severity="medium" if matches else None
    )


# core/security/input_guardrail_engine.py

async def run_input_guardrails(text: str) -> GuardrailResult:

    checks = []

    # checks.append(structural_validation(text))
    checks.append(await regex_check(text))
    checks.append(await pii_check(text))
    # checks.append(await toxicity_check(llm, text))
    # checks.append(await injection_llm_check(llm, text))
    checks.append(await scope_check(text))

    all_reasons = []
    highest_severity = None

    for result in checks:
        if not result.allowed:
            all_reasons.extend(result.reasons)
            highest_severity = result.severity or highest_severity
    print("quadrils...running")
    return GuardrailResult(
        allowed=len(all_reasons) == 0,
        reasons=all_reasons,
        severity=highest_severity
    )