"""AI Escape Room, Version 1 (Streamlit UI).

Run with:  streamlit run version1/app.py
"""

import streamlit as st

from game_master import INTRO_MESSAGE, SYSTEM_PROMPT, clean_reply, has_escaped
from llm import LLMError, chat

st.set_page_config(page_title="AI Escape Room v1", page_icon="🗝️")

AVATARS = {"assistant": "🕯️", "user": "🧑"}


def reset_game() -> None:
    st.session_state.messages = [{"role": "assistant", "content": INTRO_MESSAGE}]
    st.session_state.escaped = False


if "messages" not in st.session_state:
    reset_game()

# Sidebar: introduction, instructions and restart
with st.sidebar:
    st.header("How to play")
    st.markdown(
        "You are locked inside an old library. Type what you want to do in "
        "plain English, for example:\n"
        "- *examine the desk*\n"
        "- *take the note*\n"
        "- *try 1234 on the drawer*\n"
        "- *look behind the painting*\n\n"
        "Find the clues, solve the puzzles and open the door."
    )
    st.caption("Version 1: the Gemini Game Master runs the whole game.")
    if st.button("Restart game", use_container_width=True):
        reset_game()
        st.rerun()

st.title("🗝️ The Clockmaker's Library")
st.caption("AI Escape Room, Version 1")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar=AVATARS[msg["role"]]):
        st.markdown(msg["content"])

if st.session_state.escaped:
    st.success("You escaped! Press **Restart game** to play again.")

player_input = st.chat_input("What do you do?", disabled=st.session_state.escaped)

if player_input:
    st.session_state.messages.append({"role": "user", "content": player_input})
    with st.chat_message("user", avatar=AVATARS["user"]):
        st.markdown(player_input)

    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.spinner("The Game Master is thinking..."):
            try:
                # Gemini expects the conversation to start with a user turn,
                # so the intro message (assistant) is skipped.
                reply = chat(SYSTEM_PROMPT, st.session_state.messages[1:])
            except LLMError as err:
                st.error(str(err))
                st.session_state.messages.pop()
                st.stop()
        if has_escaped(reply):
            st.session_state.escaped = True
        reply = clean_reply(reply)
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    if st.session_state.escaped:
        # Rerun so the input box is disabled; the balloons are shown after it.
        st.session_state.celebrate = True
        st.rerun()

if st.session_state.pop("celebrate", False):
    st.balloons()
