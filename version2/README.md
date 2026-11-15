# Version 2: Reliable AI Escape Room

Python owns the rules, the LLM owns the words.

```
player text -> guard -> parser (rules first, LLM if needed) -> Engine (validate + apply)
            -> narrator (Gemini) -> check, revise up to 2 times -> reply (or template)
```

| File | Responsibility |
|------|----------------|
| `game_config.json` | Objects, items, locks, codes, hints. The only place where solutions live |
| `escape_room/state.py` | Builds the JSON game state and a public snapshot without secrets |
| `escape_room/engine.py` | One validation function per verb. Changes state only after all checks pass |
| `escape_room/parser.py` | `RuleParser` (used first, offline) and `LLMParser` (Gemini + JSON schema validation, only for messages the rules cannot understand) |
| `escape_room/guard.py` | Detects admin claims, prompt injection, secret requests, false claims |
| `escape_room/narrator.py` | Gemini narration from facts only, a leak and false-claim check, and bounded revision |
| `escape_room/llm.py` | Gemini wrapper: clear API error messages, token and call counting |
| `escape_room/game.py` | Runs one turn through all steps |

```bash
streamlit run version2/app.py   # with or without GEMINI_API_KEY
pytest version2/tests           # 76 offline tests
```
