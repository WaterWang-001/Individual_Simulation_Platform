# Dialogue Generation Guidelines (FastMCP)

This document describes backend tool `generate_event_dialogues` in `lifesim/fastmcp_server.py`.

## Purpose

Generate event-grounded dialogue history between user and assistant.

Each event experience becomes one dialogue block.

## Input Contract

Required:

- `user_profile: dict`
- `event_experiences: list[dict]`

Optional:

- `beliefs: list | None = None`
- `max_turns: int = 6`
- `refine_intention_enabled: bool = true`

## Event Fields Expected

For each event item, at least one of these should exist:

- `life_event` or `event`

For intention extraction (priority order):

- `intent`
- `intention`
- `user_intention`

If none provided, server uses a fallback intention based on event text.

## Output Contract

Returns:

- `generated_dialogues`
- `max_turns`
- `dialogues[]`

Each `dialogues[]` item:

- `event_index`
- `event`
- `intention`
- `dialogue` (list of turns)

Turn format:

```json
{ "role": "user|assistant", "content": "..." }
```

## Internal Construction

The tool uses:

- `FastConvSimulator.simulate(...)` from `simulation/fast_conv_simulator.py`
- optional intention rewrite via `refine_intention(...)` from `simulation/conv_history_generator.py`

Flow per event:

1. Parse event text and intention.
2. Optionally refine intention with profile + beliefs + event context.
3. Generate multi-turn dialogue with max turn constraint.
4. Return structured turns.

## Recommended Pairing With Event Tool

Typical backend orchestration:

1. `generate_life_events`
2. `generate_event_dialogues` using generated nodes/events

This keeps event-intention-dialogue consistent in one request chain.

## MCP Client Call Example

```python
import asyncio
import json

try:
    from mcp.server.fastmcp import Client
except ImportError:
    from fastmcp import Client

USER_PROFILE = {
    "user_id": 234857083,
    "age": "Youth (18-35 years old)", "gender": "Female",
    "area": "Cities", "employment": "Working now",
    "marital": "Never married", "income": "Middle Income",
    "personality": ["emotionally stable", "Calm"], "preferences": []
}

async def call_generate_event_dialogues(nodes: list):
    client = Client("http://localhost:8000/mcp")
    async with client:
        result = await client.call_tool("generate_event_dialogues", {
            "user_profile": USER_PROFILE,
            "event_experiences": nodes,   # nodes from generate_life_events
            "beliefs": [],
            "max_turns": 6,
            "refine_intention_enabled": True
        })
        data = json.loads(result.content[0].text)
        # data["dialogues"] is the list of per-event dialogue blocks
        return data

# Full two-step pipeline example:
async def full_pipeline():
    client = Client("http://localhost:8000/mcp")
    async with client:
        # Step 1: generate events
        r1 = await client.call_tool("generate_life_events", {
            "theme": "sport_health",
            "user_profile": USER_PROFILE,
            "expected_hours": 4,
            "start_event_index": 0,
            "max_events": 8,
            "history_events": [],
            "goal": ""
        })
        life_data = json.loads(r1.content[0].text)
        nodes = life_data["nodes"]

        # Step 2: generate dialogues
        r2 = await client.call_tool("generate_event_dialogues", {
            "user_profile": USER_PROFILE,
            "event_experiences": nodes,
            "beliefs": [],
            "max_turns": 6,
            "refine_intention_enabled": True
        })
        dialogue_data = json.loads(r2.content[0].text)
        return dialogue_data

asyncio.run(full_pipeline())
```

Key points:
- Both tools share the same `Client` context; reuse it when chaining calls
- Result is accessed via `result.content[0].text` and parsed with `json.loads`
- Each item in `dialogues` contains `event_index`, `event`, `intention`, and `dialogue` (turn list)
