from __future__ import annotations

import argparse
import json
import math
import os
import random
import threading
from typing import Any

import yaml

try:
    from fastmcp import FastMCP  # 优先用独立包
except ImportError:
    from mcp.server.fastmcp import FastMCP  # type: ignore

try:
    from models import load_model
    from tools.dense_retriever import DenseRetriever
    from engine.event_engine import OnlineLifeEventEngine
    from profiles.profile_generator import UserProfile
    from simulation.fast_conv_simulator import FastConvSimulator
    from simulation.conv_history_generator import refine_intention
except ImportError:  # pragma: no cover
    from lifesim.models import load_model  # type: ignore
    from lifesim.tools.dense_retriever import DenseRetriever  # type: ignore
    from lifesim.engine.event_engine import OnlineLifeEventEngine  # type: ignore
    from lifesim.profiles.profile_generator import UserProfile  # type: ignore
    from lifesim.simulation.fast_conv_simulator import FastConvSimulator  # type: ignore
    from lifesim.simulation.conv_history_generator import refine_intention  # type: ignore


MCP_HOST = os.getenv("LIFESIM_MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("LIFESIM_MCP_PORT", "8000"))
SERVER_CONFIG_PATH = os.getenv("LIFESIM_CONFIG_PATH", "config.yaml")

mcp = FastMCP(
    name="lifesim-backend",
    instructions="LifeSim backend MCP service. Generate life events and user intents with OnlineLifeEventEngine.",
)

_runtime_lock = threading.Lock()
_model_cache: dict[str, Any] = {}
_retriever_cache: dict[str, DenseRetriever] = {}
_config_cache: dict[str, dict[str, Any]] = {}


def _load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_server_config() -> dict[str, Any]:
    global SERVER_CONFIG_PATH
    with _runtime_lock:
        if SERVER_CONFIG_PATH in _config_cache:
            return _config_cache[SERVER_CONFIG_PATH]
        cfg = _load_config(SERVER_CONFIG_PATH)
        _config_cache[SERVER_CONFIG_PATH] = cfg
        return cfg


def _load_jsonl_data(path: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    if not os.path.exists(path):
        return data
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def _detect_theme(sequence_id: str) -> str:
    return "_".join(sequence_id.split("NYC_")[-1].split("TKY_")[-1].split("_")[:-1])


def _estimate_n_events(expected_hours: float, max_events: int) -> int:
    # Keep behavior simple: roughly one event every 3 hours.
    n = math.ceil(expected_hours / 3.0)
    n = max(1, n)
    return min(n, max_events)


def _model_key(model_cfg: dict[str, Any]) -> str:
    return json.dumps(model_cfg, sort_keys=True, ensure_ascii=False)


def _get_event_model(cfg: dict[str, Any]):
    user_m_cfg = cfg["models"]["user_model"]
    model_path = user_m_cfg.get("model_path", "")
    model_name = user_m_cfg.get("model_name") or (os.path.basename(model_path) if model_path else "")
    if not model_name:
        raise ValueError("Cannot infer model_name from config.models.user_model")

    key = _model_key(user_m_cfg)
    with _runtime_lock:
        if key in _model_cache:
            return _model_cache[key]

        model = load_model(
            model_name=model_name,
            api_key=user_m_cfg.get("api_key"),
            model_path=model_path or None,
            base_url=user_m_cfg.get("base_url"),
            vllmapi=user_m_cfg.get("vllmapi", True),
            reason=False,
        )
        _model_cache[key] = model
        return model


def _load_event_pool(
    sequence_events: list[dict[str, Any]],
    theme: str,
    event_pool_cfg_path: str = "",
) -> list[dict[str, Any]]:
    if event_pool_cfg_path and os.path.exists(event_pool_cfg_path):
        with open(event_pool_cfg_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        selected_path = mapping.get(theme) or mapping.get("entertainment")
        if selected_path and os.path.exists(selected_path):
            pool = _load_jsonl_data(selected_path)
            if pool:
                return pool

    fallback_pool: list[dict[str, Any]] = []
    for idx, item in enumerate(sequence_events):
        fallback_pool.append(
            {
                "id": str(item.get("id", f"{theme}_{idx}")),
                "event": item.get("life_event") or item.get("event", ""),
                "intent": item.get("intent", ""),
            }
        )
    return [x for x in fallback_pool if x.get("event")]


def _get_retriever(
    theme: str,
    event_database: list[dict[str, Any]],
    embedding_model_name: str,
    persist_directory: str,
    device: str = "auto",
) -> DenseRetriever:
    cache_key = f"{theme}|{embedding_model_name}|{persist_directory}|{device}"
    with _runtime_lock:
        if cache_key in _retriever_cache:
            return _retriever_cache[cache_key]

        retriever = DenseRetriever(
            model_name=embedding_model_name,
            collection_name=f"trajectory_{theme}_event_collection",
            embedding_dim=1024,
            persist_directory=persist_directory,
            distance_function="cosine",
            use_custom_embeddings=False,
            device=device,
        )
        if retriever.is_collection_empty() and event_database:
            retriever.build_index(event_database, text_field="event", id_field="id", batch_size=256)

        _retriever_cache[cache_key] = retriever
        return retriever


@mcp.tool(
    name="generate_life_events",
    description="Generate life events and intents from user profile + expected hours based on OnlineLifeEventEngine.",
)
def generate_life_events(
    theme: str,
    user_profile: dict[str, Any],
    expected_hours: float,
    start_event_index: int = 0,
    max_events: int = 8,
    history_events: list[dict[str, Any]] | None = None,
    goal: str = "",
) -> dict[str, Any]:
    if expected_hours <= 0:
        raise ValueError("expected_hours must be > 0")
    if max_events <= 0:
        raise ValueError("max_events must be > 0")

    cfg = _get_server_config()
    retriever_cfg = cfg.get("retriever", {})
    path_cfg = cfg.get("paths", {})
    event_pool_cfg_path = path_cfg.get("event_pool_cfg_path", "")
    retriever_embedding_model = retriever_cfg.get(
        "embedding_model_name",
        "/remote-home/fyduan/MODELS/Qwen3-Embedding-0.6B",
    )
    retriever_persist_directory = retriever_cfg.get(
        "persist_directory",
        "/remote-home/fyduan/exp_data/chroma_db",
    )
    retriever_device = retriever_cfg.get("device", "auto")

    events_path = cfg["paths"]["events_path"]
    events_data = _load_jsonl_data(events_path)

    # Filter sequences by theme and randomly pick one as the physical anchor
    theme_sequences = [x for x in events_data if x.get("theme") == theme]
    if not theme_sequences:
        raise ValueError(f"No sequences found for theme '{theme}' in {events_path}")
    anchor_sequence = random.choice(theme_sequences)
    sequence_id = anchor_sequence["id"]

    # Build retriever pool from ALL sequences of this theme for broader coverage
    all_theme_events: list[dict[str, Any]] = []
    for seq in theme_sequences:
        all_theme_events.extend(seq.get("events", []))

    profile_str: str
    try:
        profile_str = str(UserProfile.from_dict(user_profile))
    except Exception:
        profile_str = json.dumps(user_profile, ensure_ascii=False)

    event_database = _load_event_pool(all_theme_events, theme, event_pool_cfg_path)
    event_model = _get_event_model(cfg)
    event_retriever = _get_retriever(
        theme=theme,
        event_database=event_database,
        embedding_model_name=retriever_embedding_model,
        persist_directory=retriever_persist_directory,
        device=retriever_device,
    )

    event_engine = OnlineLifeEventEngine(events_path, model=event_model, retriever=event_retriever)
    event_engine.set_event_sequence(sequence_id)
    event_engine.set_event_index(start_event_index)

    total_events = len(anchor_sequence.get("events", []))
    remaining = max(0, total_events - start_event_index)
    planned = _estimate_n_events(expected_hours=expected_hours, max_events=max_events)
    to_generate = min(planned, remaining)

    if to_generate == 0:
        return {
            "sequence_id": sequence_id,
            "theme": theme,
            "start_event_index": start_event_index,
            "expected_hours": expected_hours,
            "requested_events": planned,
            "generated_events": 0,
            "message": "No remaining trajectory points to generate.",
            "nodes": [],
        }

    generated_raw: list[dict[str, Any]] = list(history_events or [])
    new_nodes: list[dict[str, Any]] = []
    generated_for_response: list[dict[str, Any]] = []
    active_goal = goal or f"In the next {expected_hours:.1f} hours, what the user wants to do."

    for i in range(to_generate):
        event = event_engine.generate_event(
            user_profile=profile_str,
            history_events=generated_raw,
            goal=active_goal,
        )
        generated_raw.append(event)
        life_event = event.get("life_event") or event.get("event", "")
        intent = event.get("intent", "")

        node = {
            "event_index": start_event_index + i,
            "time": event.get("time"),
            "location": event.get("location"),
            "life_event": life_event,
            "intent": intent,
            "weather": event.get("weather"),
        }
        new_nodes.append(node)
        generated_for_response.append(event)

    return {
        "sequence_id": sequence_id,
        "theme": theme,
        "longterm_goal": anchor_sequence.get("longterm_goal", ""),
        "start_event_index": start_event_index,
        "expected_hours": expected_hours,
        "requested_events": planned,
        "generated_events": len(new_nodes),
        "next_event_index": start_event_index + len(new_nodes),
        "nodes": new_nodes,
        "raw_events": generated_for_response,
    }


@mcp.tool(
    name="generate_event_dialogues",
    description="Generate user-assistant dialogues from user profile and experienced events.",
)
def generate_event_dialogues(
    user_profile: dict[str, Any],
    event_experiences: list[dict[str, Any]],
    beliefs: list[Any] | None = None,
    max_turns: int = 6,
    refine_intention_enabled: bool = True,
) -> dict[str, Any]:
    if not event_experiences:
        return {
            "generated_dialogues": 0,
            "dialogues": [],
            "message": "event_experiences is empty.",
        }
    if max_turns <= 0:
        raise ValueError("max_turns must be > 0")

    cfg = _get_server_config()
    dialogue_model = _get_event_model(cfg)
    belief_list = list(beliefs or [])

    try:
        profile_str = str(UserProfile.from_dict(user_profile))
    except Exception:
        profile_str = json.dumps(user_profile, ensure_ascii=False)

    simulator = FastConvSimulator(model=dialogue_model, max_turns=max_turns, logger_silent=True)
    outputs: list[dict[str, Any]] = []

    for idx, event in enumerate(event_experiences):
        event_item = dict(event)
        event_text = event_item.get("life_event") or event_item.get("event") or ""
        intention = (
            event_item.get("intent")
            or event_item.get("intention")
            or event_item.get("user_intention")
            or ""
        )
        intention = str(intention).strip()
        if not intention:
            intention = f"Handle this event: {event_text}".strip()

        if refine_intention_enabled:
            intention = refine_intention(
                model=dialogue_model,
                intention=intention,
                profile=profile_str,
                beliefs=belief_list,
                event=event_item,
                logger=None,
            )

        dialogue = simulator.simulate(
            event=event_item,
            intention=intention,
            beliefs=belief_list,
            profile=profile_str,
            max_turns=max_turns,
        )

        outputs.append(
            {
                "event_index": idx,
                "event": event_text,
                "intention": intention,
                "dialogue": dialogue,
            }
        )

    return {
        "generated_dialogues": len(outputs),
        "max_turns": max_turns,
        "dialogues": outputs,
    }


def main() -> None:
    global SERVER_CONFIG_PATH
    parser = argparse.ArgumentParser(description="LifeSim FastMCP backend server")
    parser.add_argument(
        "--config",
        default=SERVER_CONFIG_PATH,
        help="Server config yaml path (default: env LIFESIM_CONFIG_PATH or config.yaml)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="streamable-http",
        help="MCP transport mode",
    )
    args = parser.parse_args()
    SERVER_CONFIG_PATH = args.config
    mcp.run(transport=args.transport, host=MCP_HOST, port=MCP_PORT)


if __name__ == "__main__":
    main()
