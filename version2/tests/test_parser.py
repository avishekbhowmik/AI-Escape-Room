"""Rule parser: everyday phrasings and the bugs found while reviewing it."""

import pytest

from conftest import SOLUTION, play
from escape_room.engine import Action, same_clock_time
from escape_room.parser import RuleParser, extract_time


@pytest.fixture
def parser(config):
    return RuleParser(config)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("I want to examine the bookshelf.", {"verb": "examine", "target": "bookshelf"}),
        ("try 7-4-2-9 on the drawer", {"verb": "enter_code", "target": "drawer", "code": "7429"}),
        ("unlock the painting with the key", {"verb": "use", "item": "brass_key", "target": "painting"}),
        ("put the minute hand on the clock", {"verb": "use", "item": "minute_hand", "target": "clock"}),
        ("set the clock to ten forty", {"verb": "set_time", "target": "clock", "time": "10:40"}),
        ("type 1893 into the keypad", {"verb": "enter_code", "target": "door", "code": "1893"}),
        ("let me out", {"verb": "open", "target": "door"}),
        ("what am I carrying?", {"verb": "inventory"}),
        ("I'm stuck", {"verb": "hint"}),
    ],
)
def test_common_phrasings(parser, text, expected):
    assert parser.parse(text).to_dict() == expected


# Bugs found in the final review. Each one is a regression test now.

@pytest.mark.parametrize("text", ["read book 2", "look at the 4 books"])
def test_small_numbers_are_not_codes(parser, text):
    assert parser.parse(text).verb == "examine"


def test_get_out_means_leaving_not_taking(parser):
    assert parser.parse("get out of here").to_dict() == {"verb": "open", "target": "door"}


def test_set_clock_without_minutes_is_a_time_action(parser):
    assert parser.parse("set the clock to 10").to_dict() == {"verb": "set_time", "target": "clock"}


def test_code_without_target_asks_where(game, state):
    turn, after = play(game, state, "enter 7429")
    assert turn.result.event == "NO_TARGET"
    assert "drawer" in turn.reply and "door" in turn.reply
    assert after["objects"]["drawer"]["locked"]


def test_unknown_item_message_is_clear(game, state):
    turn, _ = play(game, state, "use the crowbar on the door")
    assert turn.reply == "There is no crowbar in this room, and you are not carrying one."


@pytest.mark.parametrize("a, b, same", [("22:40", "10:40", True), ("10:40", "10:40", True), ("10:45", "10:40", False)])
def test_clock_compares_like_a_clock_face(a, b, same):
    assert same_clock_time(a, b) is same


def test_24h_time_opens_the_clock(game, state):
    steps = SOLUTION[:8] + ["set the clock to 22:40"]
    turn, after = play(game, state, *steps)
    assert turn.result.event == "UNLOCKED"
    assert "clock_puzzle" in after["solved_puzzles"]


@pytest.mark.parametrize("text, time", [("10:40", "10:40"), ("to 1040", "10:40"), ("ten forty", "10:40"), ("9.05", "9:05")])
def test_extract_time(text, time):
    assert extract_time(text) == time


def test_parsed_action_has_no_internal_fields(parser):
    assert "reason" not in Action("look").to_dict()
