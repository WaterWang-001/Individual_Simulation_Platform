---
name: lifesim-fastmcp-backend
description: Build and use the LifeSim FastMCP backend service. Primary capabilities: (1) generate life-event trajectories with user intents given a theme, (2) generate user-assistant dialogues from profile + event experiences.
trigger: Use this skill when users ask to run LifeSim on a backend server, expose MCP tools, generate life events/intents from a theme, or generate event-grounded dialogue history.
requirements:
  - python: ">=3.10"
  - install: "Install dependencies required by lifesim and mcp server runtime"
  - env: "Frontend/client does not need model-provider key; all model/retriever config is server-side in YAML"
---

# LifeSim FastMCP Backend Skill

This skill is for backend deployment using `lifesim/fastmcp_server.py`.

## Scope

This backend provides two MCP tools:

1. `generate_life_events` — given a theme, randomly select a real physical trajectory as anchor and generate life events + intents.
2. `generate_event_dialogues` — given event nodes, generate user-assistant dialogue for each event.

## Architecture Rule

- All generation logic runs in backend (`lifesim` code + model/retriever init).
- Frontend only calls backend APIs and renders results.
- Do not expose provider keys to frontend.

## Server Entry

Main file:

- `lifesim/fastmcp_server.py`

Start server:

```bash
python lifesim/fastmcp_server.py --config config.yaml --transport streamable-http
```

Supported transport:

- `streamable-http` (recommended)
- `sse`
- `stdio`

Environment variables:

- `LIFESIM_MCP_HOST` (default `0.0.0.0`)
- `LIFESIM_MCP_PORT` (default `8000`)
- `LIFESIM_CONFIG_PATH` (default `config.yaml`)

## Tool 1: `generate_life_events`

Generate event nodes and intent for each node based on a theme and user profile.

The server randomly selects a physical trajectory (time / location / weather sequence) matching the requested theme as the generation anchor. The caller does not need to specify a `sequence_id`.

Supported themes: `sport_health` | `education` | `mental_health` | `travel` | `childcare` | `dining` | `elderlycare` | `entertainment`

Input:

- `theme: str` — one of the supported themes above
- `user_profile: dict`
- `expected_hours: float`
- `start_event_index: int = 0`
- `max_events: int = 8`
- `history_events: list[dict] | None = None`
- `goal: str = ""`

Output (core fields):

- `sequence_id` — the randomly selected anchor trajectory (for reference/reproducibility)
- `theme`
- `longterm_goal` — longterm goal of the selected trajectory
- `nodes[]` with:
  - `event_index`
  - `time`
  - `location`
  - `life_event`
  - `intent`
  - `sub_intents`
  - `weather`
- plus metadata: `generated_events`, `next_event_index`, `requested_events`

Implementation basis:

- `engine/event_engine.py::OnlineLifeEventEngine.generate_event`
- retrieval/rerank/rewrite flow and history conditioning are inherited from engine logic.

## Tool 2: `generate_event_dialogues`

Generate user-assistant dialogue for each experienced event.

Input:

- `user_profile: dict`
- `event_experiences: list[dict]` — typically the `nodes` returned by `generate_life_events`
- `beliefs: list | None = None`
- `max_turns: int = 6`
- `refine_intention_enabled: bool = true`

Output:

- `dialogues[]` with:
  - `event_index`
  - `event`
  - `intention`
  - `dialogue` (turn list: `{role, content}`)

Implementation basis:

- `simulation/fast_conv_simulator.py::FastConvSimulator.simulate`
- `simulation/conv_history_generator.py::refine_intention`

## Recommended Backend Flow

1. Call `generate_life_events` with `theme` + `user_profile` to get event trajectory + intents.
2. Pass returned `nodes` into `generate_event_dialogues`.
3. Return unified payload to frontend.

## Frontend Integration Pattern

Use a backend API gateway/BFF to map HTTP endpoints to MCP tool calls.

Example endpoint mapping:

- `POST /api/lifesim/generate-life-events` → MCP `generate_life_events`
- `POST /api/lifesim/generate-event-dialogues` → MCP `generate_event_dialogues`

Do not call model vendors directly from frontend.

## MCP Client Quick Start

Import and connect:

```python
import asyncio, json

try:
    from mcp.server.fastmcp import Client
except ImportError:
    from fastmcp import Client  # fallback

client = Client("http://localhost:8000/mcp")
```

Call `generate_life_events`:

```python
async with client:
    result = await client.call_tool("generate_life_events", {
        "theme": "sport_health",          # required
        "user_profile": USER_PROFILE,     # required
        "expected_hours": 4,              # required
        "start_event_index": 0,
        "max_events": 8,
        "history_events": [],
        "goal": ""
    })
    life_data = json.loads(result.content[0].text)
    nodes = life_data["nodes"]
```

Call `generate_event_dialogues` (pass `nodes` from step above):

```python
async with client:
    result = await client.call_tool("generate_event_dialogues", {
        "user_profile": USER_PROFILE,     # required
        "event_experiences": nodes,       # required — nodes from above
        "beliefs": [],
        "max_turns": 6,
        "refine_intention_enabled": True
    })
    dialogue_data = json.loads(result.content[0].text)
    dialogues = dialogue_data["dialogues"]
```

Result access pattern: **always** `json.loads(result.content[0].text)`.

See `scripts/verify_mcp.py` for a complete runnable example.

## References

- `references/lifesim_generation_guidelines.md`
- `references/dialogue_history_generation.md`
