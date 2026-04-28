# Tests

This folder contains isolated unit tests for each bot subsystem.

## Structure

- `tests/test_config.py` - environment/config parsing tests.
- `tests/memory/test_bot_memory.py` - memory persistence and history behavior.
- `tests/twitch/test_irc_bot.py` - IRC parsing and message formatting helpers.
- `tests/llm/test_ollama_connect.py` - Ollama request/response and fallback logic.

## Run

```bash
pytest -q
```

To run a single subsystem:

```bash
pytest tests/memory -q
pytest tests/twitch -q
pytest tests/llm -q
```
