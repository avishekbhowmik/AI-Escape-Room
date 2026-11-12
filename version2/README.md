# Version 2: Reliable AI Escape Room

Python owns the rules, the LLM owns the words.

```
player text -> guard -> parser -> Engine (validate + apply) -> narrator -> filter -> reply
```

| File | Responsibility |
|------|----------------|
| `game_config.json` | Objects, items, locks, codes, hints. The only place where solutions live |
| `escape_room/state.py` | Builds the JSON game state and a public snapshot without secrets |
| `escape_room/engine.py` | One validation function per verb. Changes state only after all checks pass |
| `escape_room/parser.py` | `LLMParser` (Gemini + JSON schema validation) and `RuleParser` (offline fallback) |
| `escape_room/guard.py` | Detects admin claims, prompt injection, secret requests, false claims |
| `escape_room/narrator.py` | Gemini narration from facts only, plus a leak and false-claim filter |
| `escape_room/game.py` | Runs one turn through all steps |

```bash
streamlit run version2/app.py   # with or without GEMINI_API_KEY
pytest version2/tests           # 50 offline tests
```
