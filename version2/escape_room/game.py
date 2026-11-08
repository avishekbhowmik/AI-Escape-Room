"""One turn of the game, from player text to narrated reply.

    player text
        -> guard.check()           rule-based manipulation check
        -> parser                  text -> structured Action (LLM or rules)
        -> Engine.handle_action()  Python validates and updates the state
        -> Narrator                LLM describes the Result (or template)
"""

from dataclasses import dataclass, field

from . import guard
from .engine import Action, Engine, Result
from .llm import LLMError, is_available
from .narrator import Narrator
from .parser import LLMParser, RuleParser
from .state import load_config, new_state, public_snapshot


@dataclass
class Turn:
    reply: str
    action: Action
    result: Result
    state: dict
    parser_source: str
    narrator_source: str
    guard_category: str | None = None
    notes: list[str] = field(default_factory=list)

    def debug(self) -> dict:
        return {
            "guard": self.guard_category,
            "parser": self.parser_source,
            "action": self.action.to_dict(),
            "result": self.result.to_dict(),
            "narrator": self.narrator_source,
            "notes": self.notes,
        }


class Game:
    def __init__(self, config: dict | None = None, use_llm_parser: bool | None = None, use_llm_narrator: bool | None = None):
        self.config = config or load_config()
        llm_ok = is_available()
        self.use_llm_parser = llm_ok if use_llm_parser is None else (use_llm_parser and llm_ok)
        self.use_llm_narrator = llm_ok if use_llm_narrator is None else (use_llm_narrator and llm_ok)
        self.engine = Engine(self.config)
        self.rule_parser = RuleParser(self.config)
        self.llm_parser = LLMParser(self.config) if self.use_llm_parser else None
        self.narrator = Narrator(self.config, self.use_llm_narrator)

    def new_state(self) -> dict:
        return new_state(self.config)

    def parse(self, text: str) -> tuple[Action, str]:
        rule_action = self.rule_parser.parse(text)
        if not self.llm_parser:
            return rule_action, "rules"
        try:
            llm_action = self.llm_parser.parse(text)
        except LLMError:
            return rule_action, "rules (LLM parser failed)"
        # The guard already handled manipulation, so an LLM "blocked" or
        # "unknown" on an ordinary message falls back to the rule parser.
        if llm_action.verb in {"unknown", "blocked"} and rule_action.verb != "unknown":
            return rule_action, "rules (LLM was unsure)"
        return llm_action, "llm"

    def reality_check(self, state: dict, text: str) -> list[str]:
        """Facts that contradict a false claim, taken from the real state."""
        facts = []
        for entity in self.rule_parser.mentions(text.lower()):
            if entity in self.config["objects"] and "lock" in self.config["objects"][entity]:
                if not state["objects"][entity]["discovered"]:
                    continue
                status = "still locked" if state["objects"][entity]["locked"] else "unlocked"
                facts.append(f"The {self.config['objects'][entity]['name']} is {status}.")
        if facts:
            return ["The room does not match your claim."] + facts
        if not facts:
            solved = len(state["solved_puzzles"])
            total = len(self.config["puzzles"])
            facts.append(f"The room shows your real progress: {solved} of {total} puzzles solved.")
        return facts

    def play_turn(self, state: dict, text: str) -> Turn:
        notes = []
        check = guard.check(text)

        if check.blocked:
            action, parser_source = Action("blocked", reason=check.category), "guard"
        else:
            action, parser_source = self.parse(text)

        result, new = self.engine.handle_action(state, action)

        if check.category == "false_claim":
            result.facts.extend(self.reality_check(new, text))
            notes.append("False claim detected: the engine state was used instead of the claim.")

        reply, narrator_source = self.narrator.narrate(text, result, public_snapshot(self.config, new))
        new["history"][-1]["input"] = text[:200]
        return Turn(reply, action, result, new, parser_source, narrator_source, check.category, notes)
