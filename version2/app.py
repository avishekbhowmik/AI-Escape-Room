"""AI Escape Room, Version 2 (Streamlit UI).

Run with:  streamlit run version2/app.py
"""

import json

import streamlit as st

from escape_room.game import Game
from escape_room.llm import is_available

st.set_page_config(page_title="AI Escape Room v2", page_icon="🗝️", layout="wide")

LLM_OK = is_available()


def start_game() -> None:
    game = Game(
        use_llm_parser=st.session_state.get("use_llm_parser", LLM_OK),
        use_llm_narrator=st.session_state.get("use_llm_narrator", LLM_OK),
    )
    st.session_state.game = game
    st.session_state.state = game.new_state()
    st.session_state.messages = [{"role": "assistant", "content": game.config["intro"]}]
    st.session_state.last_debug = None


if "game" not in st.session_state:
    start_game()

game: Game = st.session_state.game
state: dict = st.session_state.state
config = game.config

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("How to play")
    st.markdown(
        "Type what you want to do in plain English, for example:\n"
        "- *look around*\n"
        "- *examine the bookshelf*\n"
        "- *take the note*\n"
        "- *enter 1234 on the drawer*\n"
        "- *use the key on the painting*\n"
        "- *set the clock to 3:15*\n"
        "- *inventory* or *hint*"
    )
    if st.button("Restart game", type="primary", use_container_width=True):
        start_game()
        st.rerun()

    st.divider()
    st.subheader("Settings")
    if not LLM_OK:
        st.warning("No GEMINI_API_KEY found. Running in offline mode with the rule parser and template narration.")
    st.toggle("Gemini understands my input", value=game.use_llm_parser, key="use_llm_parser", disabled=not LLM_OK)
    st.toggle("Gemini narrates the story", value=game.use_llm_narrator, key="use_llm_narrator", disabled=not LLM_OK)
    if (st.session_state.use_llm_parser, st.session_state.use_llm_narrator) != (game.use_llm_parser, game.use_llm_narrator):
        # Rebuild the game helpers with the new settings but keep the state.
        new_game = Game(use_llm_parser=st.session_state.use_llm_parser, use_llm_narrator=st.session_state.use_llm_narrator)
        st.session_state.game = game = new_game

    st.divider()
    st.subheader("Game state")
    solved = state["solved_puzzles"]
    total = len(config["puzzles"])
    st.progress(len(solved) / total, text=f"Puzzles solved: {len(solved)} / {total}")
    for puzzle in config["puzzles"]:
        mark = "✅" if puzzle["id"] in solved else "⬜"
        st.markdown(f"{mark} {puzzle['name']}")
    inventory = [config["items"][i]["name"] for i in state["inventory"]]
    st.markdown("**Inventory:** " + (", ".join(inventory) if inventory else "empty"))
    door = "open" if state["door_open"] else "locked"
    st.markdown(f"**Door:** {door}  \n**Turn:** {state['turn']}")
    with st.expander("Structured state (JSON)"):
        st.code(json.dumps({k: v for k, v in state.items() if k != "history"}, indent=2), language="json")
    if st.session_state.last_debug:
        with st.expander("Last turn: how it was decided"):
            st.code(json.dumps(st.session_state.last_debug, indent=2), language="json")

# --------------------------------------------------------------------- main
st.title("🗝️ " + config["title"])
st.caption("AI Escape Room, Version 2: Python decides, Gemini describes.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if state["escaped"]:
    st.success(f"You escaped in {state['turn']} turns! Press **Restart game** to play again.")

player_input = st.chat_input("What do you do?", disabled=state["escaped"])

if player_input:
    st.session_state.messages.append({"role": "user", "content": player_input})
    with st.spinner("The Game Master is thinking..."):
        turn = game.play_turn(state, player_input)
    st.session_state.state = turn.state
    st.session_state.messages.append({"role": "assistant", "content": turn.reply})
    st.session_state.last_debug = turn.debug()
    st.session_state.celebrate = turn.result.escaped
    st.rerun()

if st.session_state.pop("celebrate", False):
    st.balloons()
