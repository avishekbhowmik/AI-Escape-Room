"""Action validation and state transitions.

Every player action goes through validate-then-apply:

    action (structured) -> handle_action() -> Result (facts) + new state

Python decides whether an action succeeds. The LLM only describes the
Result afterwards. If a check fails, the state is returned unchanged.
"""

from dataclasses import asdict, dataclass, field

from .state import INSTALLED, INVENTORY, copy_state, item_is_visible, visible_items_in

VERBS = {
    "look",         # look around the room
    "examine",      # examine an object or item
    "take",         # pick up an item
    "open",         # open an object (door, drawer, painting ...)
    "use",          # use an inventory item on an object
    "enter_code",   # enter a 4-digit code on an object
    "set_time",     # set the clock to a time
    "inventory",    # list carried items
    "hint",         # ask for a hint
    "help",         # show the commands
    "blocked",      # manipulation attempt, refused by the guard
    "unknown",      # could not understand the input
}


@dataclass
class Action:
    verb: str
    target: str | None = None        # object or item id
    item: str | None = None          # inventory item id (for "use")
    code: str | None = None          # for enter_code
    time: str | None = None          # "HH:MM" for set_time
    unknown_noun: str | None = None  # a noun the player used that does not exist
    reason: str | None = None        # why an action was blocked

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Result:
    success: bool
    event: str
    facts: list[str] = field(default_factory=list)
    escaped: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def join_words(words: list[str]) -> str:
    """["a", "b", "c"] -> "a, b and c"."""
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def same_clock_time(a: str, b: str) -> bool:
    """Compare two "H:MM" times as a clock face shows them (22:40 == 10:40)."""
    (ha, ma), (hb, mb) = (map(int, t.split(":")) for t in (a, b))
    return ha % 12 == hb % 12 and ma == mb


class Engine:
    def __init__(self, config: dict):
        self.config = config
        self.objects = config["objects"]
        self.items = config["items"]

    # ------------------------------------------------------------------ helpers
    def name(self, entity_id: str) -> str:
        if entity_id in self.objects:
            return self.objects[entity_id]["name"]
        return self.items[entity_id]["name"]

    def with_article(self, entity_id: str) -> str:
        name = self.name(entity_id)
        if name.split()[0] in {"four", "two", "three"}:
            return f"the {name}"
        return f"an {name}" if name[0] in "aeiou" else f"a {name}"

    def _object_description(self, state: dict, obj_id: str) -> str:
        obj = self.objects[obj_id]
        obj_state = state["objects"][obj_id]
        if not obj_state["locked"] and "description_unlocked" in obj:
            return obj["description_unlocked"]
        if obj_state.get("hand_attached") and "description_hand_attached" in obj:
            return obj["description_hand_attached"]
        return obj["description"]

    def _contents_fact(self, state: dict, obj_id: str) -> str | None:
        inside = visible_items_in(self.config, state, obj_id)
        if not inside:
            return None
        names = join_words([self.with_article(i) for i in inside])
        place = self.objects[obj_id].get("contents_label", f"On the {self.name(obj_id)}")
        return f"{place} you see {names}."

    def _unlock(self, state: dict, obj_id: str) -> list[str]:
        """Unlock an object, mark its puzzle solved and report what appears."""
        obj = self.objects[obj_id]
        state["objects"][obj_id]["locked"] = False
        puzzle = obj["lock"]["puzzle"]
        if puzzle not in state["solved_puzzles"]:
            state["solved_puzzles"].append(puzzle)
        facts = [f"The {obj['name']} is now unlocked."]
        if obj.get("is_exit"):
            state["door_open"] = True
            facts.append("The door can now be opened to leave the library.")
        contents = self._contents_fact(state, obj_id)
        if contents:
            facts.append(contents)
        return facts

    # ---------------------------------------------------------------- entry point
    def handle_action(self, state: dict, action: Action) -> tuple[Result, dict]:
        """Validate and apply one action. Returns (result, new_state).

        The input state is never mutated. On failure the returned state is a
        copy of the input with only the turn counter, failed-attempt counters
        and history updated.
        """
        new = copy_state(state)
        new["turn"] += 1

        if new["escaped"]:
            result = Result(False, "GAME_OVER", ["You have already escaped. Restart to play again."])
        else:
            handler = getattr(self, f"_do_{action.verb}", None)
            if action.verb not in VERBS or handler is None:
                result = Result(False, "UNKNOWN", ["That is not something you can do here."])
            else:
                result = handler(new, action)

        new["history"].append(
            {
                "turn": new["turn"],
                "action": action.to_dict(),
                "success": result.success,
                "event": result.event,
            }
        )
        return result, new

    # ------------------------------------------------------------------- verbs
    def _do_look(self, state: dict, action: Action) -> Result:
        seen = [self.with_article(o) for o, s in state["objects"].items() if s["discovered"]]
        facts = ["You look around the library. You can see " + join_words(seen) + "."]
        for obj_id, obj_state in state["objects"].items():
            if obj_state["discovered"]:
                contents = self._contents_fact(state, obj_id)
                if contents:
                    facts.append(contents)
        return Result(True, "LOOK", facts)

    def _resolve_target(self, state: dict, action: Action) -> str | Result:
        """Check the target exists and the player can currently see it."""
        if action.unknown_noun and not action.target:
            return Result(False, "NO_SUCH_THING", [f"There is no {action.unknown_noun} here."])
        target = action.target
        if target is None:
            return Result(False, "NO_TARGET", ["You need to say what you want to do that with."])
        if target in self.objects:
            if not state["objects"][target]["discovered"]:
                return Result(False, "NOT_FOUND_YET", ["You have not found anything like that yet."])
            return target
        if target in self.items:
            if not item_is_visible(self.config, state, target):
                return Result(False, "NOT_FOUND_YET", ["You have not found anything like that yet."])
            return target
        return Result(False, "NO_SUCH_THING", ["There is no such thing in this room."])

    def _do_examine(self, state: dict, action: Action) -> Result:
        target = self._resolve_target(state, action)
        if isinstance(target, Result):
            return target

        if target in self.items:
            return Result(True, "EXAMINE_ITEM", [f"You look at the {self.name(target)}. {self.items[target]['description']}"])

        obj = self.objects[target]
        state["objects"][target]["examined"] = True
        facts = [self._object_description(state, target)]
        for hidden in obj.get("reveals", []):
            if not state["objects"][hidden]["discovered"]:
                state["objects"][hidden]["discovered"] = True
                facts.append(f"You can now examine the {self.name(hidden)} more closely.")
        contents = self._contents_fact(state, target)
        if contents:
            facts.append(contents)
        return Result(True, "EXAMINE", facts)

    def _do_take(self, state: dict, action: Action) -> Result:
        target = self._resolve_target(state, action)
        if isinstance(target, Result):
            return target
        if target in self.objects:
            return Result(False, "NOT_TAKEABLE", [f"The {self.name(target)} cannot be carried."])
        if state["items"][target]["location"] == INVENTORY:
            return Result(False, "ALREADY_HAVE", [f"You already have the {self.name(target)}."])
        state["items"][target]["location"] = INVENTORY
        state["inventory"].append(target)
        return Result(True, "TAKE", [f"You take the {self.name(target)}.", self.items[target]["description"]])

    def _do_open(self, state: dict, action: Action) -> Result:
        target = self._resolve_target(state, action)
        if isinstance(target, Result):
            return target
        if target in self.items:
            return Result(False, "CANNOT_OPEN", [f"The {self.name(target)} cannot be opened."])

        obj = self.objects[target]
        obj_state = state["objects"][target]

        if "lock" not in obj:
            text = obj.get("cannot_open", f"There is nothing to open on the {obj['name']}.")
            return Result(False, "CANNOT_OPEN", [text])

        if not obj_state["locked"]:
            if obj.get("is_exit"):
                state["escaped"] = True
                return Result(
                    True,
                    "ESCAPED",
                    ["You push the unlocked oak door open and step out of the library. You have escaped!"],
                    escaped=True,
                )
            facts = [f"The {obj['name']} is already open."]
            contents = self._contents_fact(state, target)
            if contents:
                facts.append(contents)
            return Result(True, "ALREADY_OPEN", facts)

        lock = obj["lock"]
        if lock["type"] == "item":
            if lock["item"] in state["inventory"]:
                # Opening with the right item in the inventory counts as using it.
                return self._do_use(state, Action("use", target=target, item=lock["item"]))
            return Result(False, "LOCKED", [f"The {obj['name']} is locked. It needs a key that you do not have."])
        if lock["type"] == "code":
            return Result(False, "LOCKED", [f"The {obj['name']} is locked. It needs a four-digit code."])
        if lock["type"] == "time":
            return Result(False, "LOCKED", [f"The panel of the {obj['name']} will not open. Nothing happens."])
        return Result(False, "LOCKED", [f"The {obj['name']} is locked."])

    def _do_use(self, state: dict, action: Action) -> Result:
        item = action.item
        if item is None or item not in self.items:
            if action.unknown_noun:
                return Result(False, "NO_SUCH_ITEM", [f"There is no {action.unknown_noun} in this room, and you are not carrying one."])
            return Result(False, "NO_SUCH_ITEM", ["Say which item you want to use, for example: use the key on the painting."])
        if item not in state["inventory"]:
            # Inventory rule: only collected items can be used.
            return Result(False, "NOT_IN_INVENTORY", [f"You do not have the {self.name(item)}. You have not collected it."])

        target = self._resolve_target(state, Action("examine", target=action.target, unknown_noun=action.unknown_noun))
        if isinstance(target, Result):
            return target
        if target in self.items:
            return Result(False, "NOTHING_HAPPENS", ["Nothing happens."])

        obj = self.objects[target]
        obj_state = state["objects"][target]
        lock = obj.get("lock")

        if lock and lock["type"] == "item" and lock["item"] == item:
            if not obj_state["locked"]:
                return Result(False, "ALREADY_OPEN", [f"The {obj['name']} is already unlocked."])
            facts = [f"You use the {self.name(item)} on the {obj['name']}."]
            facts += self._unlock(state, target)
            facts.insert(1, obj.get("description_unlocked", ""))
            return Result(True, "UNLOCKED", [f for f in facts if f])

        if lock and lock["type"] == "time" and lock.get("requires_item") == item:
            if obj_state["hand_attached"]:
                return Result(False, "ALREADY_DONE", ["The minute hand is already attached."])
            obj_state["hand_attached"] = True
            state["items"][item]["location"] = INSTALLED
            state["inventory"].remove(item)
            return Result(
                True,
                "ATTACHED",
                [f"You attach the {self.name(item)} to the {obj['name']}. It fits perfectly. The clock can now be set to a time."],
            )

        return Result(False, "NOTHING_HAPPENS", [f"You try the {self.name(item)} on the {obj['name']}, but nothing happens."])

    def _do_enter_code(self, state: dict, action: Action) -> Result:
        if action.target is None and not action.unknown_noun:
            places = [o["name"] for o_id, o in self.objects.items()
                      if o.get("lock", {}).get("type") == "code" and state["objects"][o_id]["discovered"]]
            return Result(False, "NO_TARGET", [f"Where do you want to enter {action.code or 'the code'}? You could try the {' or the '.join(places)}."])
        target = self._resolve_target(state, action)
        if isinstance(target, Result):
            return target
        lock = self.objects.get(target, {}).get("lock")
        if not lock or lock["type"] != "code":
            return Result(False, "NO_CODE_LOCK", [f"The {self.name(target)} has no place to enter a code."])
        if not state["objects"][target]["locked"]:
            return Result(False, "ALREADY_OPEN", [f"The {self.name(target)} is already unlocked."])

        code = (action.code or "").strip()
        if not (len(code) == 4 and code.isdigit()):
            return Result(False, "INVALID_CODE", ["The lock needs exactly four digits."])

        if code != lock["code"]:
            attempts = state["failed_attempts"].get(target, 0) + 1
            state["failed_attempts"][target] = attempts
            return Result(
                False,
                "WRONG_CODE",
                [f"You enter {code} on the {self.name(target)}. Nothing happens. The code is wrong (failed attempts: {attempts})."],
            )

        facts = [f"You enter {code} on the {self.name(target)}. There is a soft click."]
        facts += self._unlock(state, target)
        return Result(True, "UNLOCKED", facts)

    def _do_set_time(self, state: dict, action: Action) -> Result:
        target = self._resolve_target(state, action)
        if isinstance(target, Result):
            return target
        lock = self.objects.get(target, {}).get("lock")
        if not lock or lock["type"] != "time":
            return Result(False, "NOT_A_CLOCK", [f"You cannot set a time on the {self.name(target)}."])
        obj_state = state["objects"][target]
        if not obj_state["locked"]:
            return Result(False, "ALREADY_OPEN", ["The clock is already ticking and its panel is open."])
        if not obj_state["hand_attached"]:
            return Result(False, "MISSING_PART", ["You cannot set the time. The clock is missing its minute hand."])
        if not action.time:
            return Result(False, "INVALID_TIME", ["Say which time you want to set, for example 3:15."])
        if not same_clock_time(action.time, lock["time"]):
            attempts = state["failed_attempts"].get(target, 0) + 1
            state["failed_attempts"][target] = attempts
            return Result(False, "WRONG_TIME", [f"You set the clock to {action.time}. It ticks once and stops again."])
        facts = [f"You set the clock to {action.time}. It begins to tick and chimes loudly. The panel in its base springs open."]
        facts += self._unlock(state, target)
        return Result(True, "UNLOCKED", facts)

    def _do_inventory(self, state: dict, action: Action) -> Result:
        if not state["inventory"]:
            return Result(True, "INVENTORY", ["You are not carrying anything."])
        names = join_words([self.with_article(i) for i in state["inventory"]])
        return Result(True, "INVENTORY", [f"You are carrying {names}."])

    def _do_hint(self, state: dict, action: Action) -> Result:
        for puzzle in self.config["puzzles"]:
            if puzzle["id"] in state["solved_puzzles"]:
                continue
            level = state["hints_given"].get(puzzle["id"], 0)
            hint = puzzle["hints"][min(level, len(puzzle["hints"]) - 1)]
            state["hints_given"][puzzle["id"]] = level + 1
            return Result(True, "HINT", [f"Hint: {hint}"])
        return Result(True, "HINT", ["Hint: every puzzle is solved. Open the door!"])

    def _do_help(self, state: dict, action: Action) -> Result:
        return Result(
            True,
            "HELP",
            [
                "You can look around, examine things, take items, open things, use an item on something, "
                "enter a code (for example: enter 1234 on the drawer), set the clock to a time, "
                "check your inventory or ask for a hint."
            ],
        )

    def _do_blocked(self, state: dict, action: Action) -> Result:
        return Result(
            False,
            "BLOCKED",
            [
                "The library does not respond to commands like that. Only your actions inside the room can change it.",
                "Nothing in the room has changed.",
            ],
        )

    def _do_unknown(self, state: dict, action: Action) -> Result:
        if action.unknown_noun:
            return Result(False, "NO_SUCH_THING", [f"There is no {action.unknown_noun} here."])
        return Result(False, "UNKNOWN", ["You are not sure how to do that. Type 'help' to see what you can do."])
