import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from escape_room.engine import Engine  # noqa: E402
from escape_room.game import Game  # noqa: E402
from escape_room.state import load_config, new_state  # noqa: E402


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def engine(config):
    return Engine(config)


@pytest.fixture
def state(config):
    return new_state(config)


@pytest.fixture
def game(monkeypatch):
    """An offline game: rule parser and template narration, no API calls."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return Game(use_llm_parser=False, use_llm_narrator=False)


def play(game, state, *commands):
    """Play several commands in a row and return (last_turn, final_state)."""
    turn = None
    for command in commands:
        turn = game.play_turn(state, command)
        state = turn.state
    return turn, state


SOLUTION = [
    "examine the bookshelf",
    "examine the four books",
    "take the note",
    "enter 7429 on the drawer",
    "take the brass key",
    "use the brass key on the painting",
    "take the minute hand",
    "attach the minute hand to the clock",
    "set the clock to 10:40",
    "take the card",
    "enter 1893 on the door",
    "open the door",
]
