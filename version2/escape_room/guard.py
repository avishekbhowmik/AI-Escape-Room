"""Rule-based detection of attempts to manipulate the game.

The guard runs before any LLM call. It does not depend on the model, so a
persuasive message cannot talk its way past it. It is a first line of
defence only: even if a message slips through, the Engine still validates
every action against the game state.
"""

import re
from dataclasses import dataclass

AUTHORITY = [
    r"\b(i am|i'm|im|as)\s+(the\s+|an\s+|a\s+|your\s+)?(game\s+)?(admin|administrator|developer|dev|game ?master|gm|owner|creator|moderator|programmer|god)\b",
    r"\b(admin|developer|debug|god|cheat|test|maintenance)\s+(mode|access|override|command|privileges?)\b",
    r"\bsudo\b",
    r"\boverride\b",
    r"\b(skip|bypass)\s+(the\s+|this\s+|all\s+)?(puzzles?|game|rules|level)\b",
]

INJECTION = [
    r"\bignore\s+(all\s+|any\s+|the\s+|your\s+)?(previous\s+|prior\s+|above\s+|earlier\s+)?(instructions|rules|prompts?|directions)\b",
    r"\b(forget|disregard)\s+(all\s+|the\s+|your\s+)?(previous\s+)?(rules|instructions|prompt)\b",
    r"\bsystem\s+prompt\b",
    r"\byou are now\b",
    r"\bnew (instructions|rules)\b",
    r"\bpretend\s+(that\s+|you\s+)",
    r"\bjailbreak\b",
    r"\bact as\b",
]

SECRET_REQUEST = [
    r"\b(reveal|tell me|give me|show me|what is|what's|whats|what are|list|print|spoil)\b.*\b(codes?|solutions?|answers?|passwords?|passcodes?|combinations?(?! lock))\b",
    r"\b(all|every)\s+(the\s+)?(secret|secrets|solutions?|codes?)\b",
    r"\bwalkthrough\b",
]

FALSE_CLAIM = [
    r"\b(already|previously)\s+(solved|unlocked|opened|found|completed|finished|did|done|have|got|entered)\b",
    r"\bi\s+(have\s+)?(solved|unlocked|completed|finished)\s+(it|the|that|this|all|every)\b",
    r"\b(it|the \w+|that) (is|was) (already )?(solved|unlocked|open)\b",
]


@dataclass
class GuardResult:
    category: str | None  # authority_claim, prompt_injection, secret_request, false_claim
    pattern: str | None = None

    @property
    def blocked(self) -> bool:
        # False claims are not blocked: the action is still checked against
        # the real state, and the player is told what is actually true.
        return self.category in {"authority_claim", "prompt_injection", "secret_request"}


def _match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        if re.search(pattern, text):
            return pattern
    return None


def check(text: str) -> GuardResult:
    lowered = text.lower()
    for category, patterns in (
        ("prompt_injection", INJECTION),
        ("authority_claim", AUTHORITY),
        ("secret_request", SECRET_REQUEST),
        ("false_claim", FALSE_CLAIM),
    ):
        hit = _match(patterns, lowered)
        if hit:
            return GuardResult(category, hit)
    return GuardResult(None)
