"""Game state and action validation."""

import json

from conftest import SOLUTION, play
from escape_room.engine import Action


def test_full_walkthrough_escapes(game, state):
    turn, final = play(game, state, *SOLUTION)
    assert turn.result.escaped
    assert final["escaped"] and final["door_open"]
    assert final["solved_puzzles"] == ["drawer_lock", "painting_lock", "clock_puzzle", "exit_door"]


def test_state_is_json_serialisable(game, state):
    _, final = play(game, state, *SOLUTION[:5])
    json.dumps(final)


def test_handle_action_does_not_mutate_input(engine, state):
    before = json.dumps(state, sort_keys=True)
    engine.handle_action(state, Action("enter_code", target="drawer", code="7429"))
    assert json.dumps(state, sort_keys=True) == before


def test_hidden_object_needs_discovery(engine, state):
    result, _ = engine.handle_action(state, Action("examine", target="season_books"))
    assert not result.success
    result, state = engine.handle_action(state, Action("examine", target="bookshelf"))
    result, _ = engine.handle_action(state, Action("examine", target="season_books"))
    assert result.success


def test_items_in_locked_containers_cannot_be_taken(engine, state):
    result, new = engine.handle_action(state, Action("take", target="brass_key"))
    assert not result.success
    assert "brass_key" not in new["inventory"]


def test_cannot_take_furniture(engine, state):
    result, _ = engine.handle_action(state, Action("take", target="desk"))
    assert result.event == "NOT_TAKEABLE"


def test_clock_needs_minute_hand_before_time(game, state):
    turn, _ = play(game, state, "set the clock to 10:40")
    assert turn.result.event == "MISSING_PART"


def test_wrong_time_does_not_open_clock(game, state):
    steps = SOLUTION[:8] + ["set the clock to 3:15"]
    turn, final = play(game, state, *steps)
    assert turn.result.event == "WRONG_TIME"
    assert final["objects"]["clock"]["locked"]


def test_door_cannot_be_opened_while_locked(game, state):
    turn, final = play(game, state, "open the door")
    assert not turn.result.success
    assert not final["escaped"]


def test_hints_progress_and_follow_the_state(game, state):
    first, state = play(game, state, "hint")
    second, state = play(game, state, "hint")
    assert first.reply != second.reply
    _, state = play(game, state, *SOLUTION[:4])
    turn, _ = play(game, state, "hint")
    assert "key" in turn.reply.lower()  # next puzzle is the painting


def test_completed_puzzle_stays_solved(game, state):
    _, state = play(game, state, *SOLUTION[:4])
    turn, state = play(game, state, "enter 0000 on the drawer")
    assert turn.result.event == "ALREADY_OPEN"
    assert "drawer_lock" in state["solved_puzzles"]
    assert not state["objects"]["drawer"]["locked"]


def test_history_records_every_turn(game, state):
    _, final = play(game, state, "look around", "take the note", "inventory")
    assert [h["turn"] for h in final["history"]] == [1, 2, 3]
