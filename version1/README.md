# Version 1: Interactive AI Escape Room

The LLM is the whole game. `game_master.py` holds one system prompt with the story,
all objects, the puzzle solutions and the rules. `app.py` sends the full chat history
to Gemini each turn and ends the game when the reply contains `[ESCAPED]`.

```bash
streamlit run version1/app.py     # needs GEMINI_API_KEY in .env
```

Scope (as defined in the assignment): players are assumed to play normally.
Cheating and prompt injection are not handled. See the main README for the
problems this causes and how Version 2 fixes them.
