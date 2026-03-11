# Life Event Generation Guidelines (FastMCP)

This document describes how to use backend tool `generate_life_events` in `lifesim/fastmcp_server.py`.

## Purpose

Generate life events and user intents for each trajectory node from:

- theme (e.g. `sport_health`, `entertainment`)
- user profile
- expected time horizon

Core implementation references:

- `engine/event_engine.py::OnlineLifeEventEngine`
- especially `generate_event(...)`

## Input Contract

Required:

- `theme: str`
- `user_profile: dict`
- `expected_hours: float`

Optional:

- `start_event_index: int = 0`
- `max_events: int = 8`
- `history_events: list[dict] | None = None`
- `goal: str = ""`

Supported theme values:

- `sport_health`
- `education`
- `mental_health`
- `travel`
- `childcare`
- `dining`
- `elderlycare`
- `entertainment`

## Output Contract

The returned `nodes` list is the stable frontend-facing structure:

- `event_index`
- `time`
- `location`
- `life_event`
- `intent`
- `sub_intents`
- `weather`

Server also returns metadata:

- `sequence_id` — the randomly selected physical trajectory anchor (useful for reproducibility/debugging)
- `theme`
- `longterm_goal` — longterm goal from the selected anchor trajectory
- `generated_events`
- `next_event_index`
- `requested_events`

## Generation Logic

1. Filter all trajectory sequences from `paths.events_path` where `theme` matches.
2. Randomly select one sequence as the **physical anchor** (provides time / location / weather context).
3. Build retriever index from **all** sequences of that theme (wider event reference pool).
4. Convert profile dict into profile text (`UserProfile.from_dict` if possible).
5. Call `event_engine.set_event_sequence(anchor_id)` to bind the physical timeline.
6. For each node:
   - call `OnlineLifeEventEngine.generate_event(...)`
   - use history as context
   - produce rewritten `life_event` and `intent` when candidates are available.

## Server-Side Config

All infra params are from YAML (not API payload):

- `paths.events_path`
- `paths.event_pool_cfg_path` (optional)
- `models.user_model.*`
- `retriever.embedding_model_name`
- `retriever.persist_directory`
- `retriever.device`

## Operational Notes

- The service caches model/retriever instances in process memory.
- `expected_hours` is mapped to event count by server heuristic (about one event per 3 hours).
- If no remaining event points exist for `start_event_index`, returns empty `nodes` with message.
- The selected `sequence_id` is returned for reference but should not be treated as a stable identifier across calls (it is randomly chosen each time).

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

async def call_generate_life_events():
    client = Client("http://localhost:8000/mcp")
    async with client:
        result = await client.call_tool("generate_life_events", {
            "theme": "sport_health",
            "user_profile": USER_PROFILE,
            "expected_hours": 4,
            "start_event_index": 0,
            "max_events": 8,
            "history_events": [],
            "goal": ""
        })
        data = json.loads(result.content[0].text)
        # data["nodes"] contains the event list
        # data["sequence_id"], data["theme"], data["longterm_goal"] are metadata
        return data

asyncio.run(call_generate_life_events())
```

Key points:
- Server URL: `http://localhost:8000/mcp` (default; adjust host/port via env vars)
- Result is accessed via `result.content[0].text` and parsed with `json.loads`
- `nodes` in the returned dict are passed directly to `generate_event_dialogues`
