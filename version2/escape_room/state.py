"""Game configuration loading and the structured game state.

The game state is a plain, JSON-serialisable dictionary. It is the single
source of truth for what has happened in the game. The LLM never edits it.
"""

import copy
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "game_config.json"

INVENTORY = "inventory"
INSTALLED = "installed"  # an item that has been fitted into an object


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def new_state(config: dict) -> dict:
    """Build the starting state from the configuration."""
    objects = {}
    for obj_id, obj in config["objects"].items():
        objects[obj_id] = {
            "discovered": obj.get("visible", True),
            "locked": "lock" in obj,
            "examined": False,
        }
        if obj.get("lock", {}).get("type") == "time":
            objects[obj_id]["hand_attached"] = False

    return {
        "turn": 0,
        "objects": objects,
        "items": {item_id: {"location": item["location"]} for item_id, item in config["items"].items()},
        "inventory": [],
        "solved_puzzles": [],
        "failed_attempts": {},
        "hints_given": {},
        "door_open": False,
        "escaped": False,
        "history": [],
    }


def copy_state(state: dict) -> dict:
    return copy.deepcopy(state)


def is_container_open(config: dict, state: dict, obj_id: str) -> bool:
    """Items inside an object can only be seen when it is not locked."""
    if obj_id not in config["objects"]:
        return False
    return not state["objects"][obj_id]["locked"]


def item_is_visible(config: dict, state: dict, item_id: str) -> bool:
    """An item is visible if the player holds it or it sits in an open, known container."""
    location = state["items"][item_id]["location"]
    if location == INVENTORY:
        return True
    if location == INSTALLED:
        return False
    return state["objects"][location]["discovered"] and is_container_open(config, state, location)


def visible_items_in(config: dict, state: dict, obj_id: str) -> list[str]:
    return [
        item_id
        for item_id, item_state in state["items"].items()
        if item_state["location"] == obj_id and item_is_visible(config, state, item_id)
    ]


def public_snapshot(config: dict, state: dict) -> dict:
    """A view of the state that is safe to show the player or the LLM.

    It contains names and statuses only. No codes, times or solutions.
    """
    return {
        "visible_objects": [
            config["objects"][o]["name"] for o, s in state["objects"].items() if s["discovered"]
        ],
        "inventory": [config["items"][i]["name"] for i in state["inventory"]],
        "locked": [
            config["objects"][o]["name"]
            for o, s in state["objects"].items()
            if s["discovered"] and s["locked"]
        ],
        "solved_puzzles": list(state["solved_puzzles"]),
        "door_open": state["door_open"],
        "escaped": state["escaped"],
    }
