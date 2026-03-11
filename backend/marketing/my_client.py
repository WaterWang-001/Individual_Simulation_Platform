import asyncio
import json
import os
import time
from pathlib import Path

from fastmcp import Client


def _ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _log(message: str) -> None:
    print(f"[{_ts()}] {message}", flush=True)


async def _call_tool_with_trace(
    client: Client,
    tool_name: str,
    params: dict,
):
    _log(f"START tool={tool_name} params={json.dumps(params, ensure_ascii=False)}")
    start = time.perf_counter()

    try:
        result = await client.call_tool(tool_name, params)
    except Exception as exc:
        elapsed = time.perf_counter() - start
        _log(f"ERROR tool={tool_name} elapsed={elapsed:.2f}s error={exc}")
        raise

    elapsed = time.perf_counter() - start
    _log(f"DONE tool={tool_name} elapsed={elapsed:.2f}s")
    return result


def _pretty(data: object) -> str:
    normalized = data
    if hasattr(normalized, "data") and getattr(normalized, "data") is not None:
        normalized = getattr(normalized, "data")
    elif hasattr(normalized, "structured_content") and getattr(normalized, "structured_content") is not None:
        normalized = getattr(normalized, "structured_content")
    elif hasattr(normalized, "model_dump"):
        normalized = normalized.model_dump()
    elif hasattr(normalized, "dict"):
        normalized = normalized.dict()

    try:
        return json.dumps(normalized, ensure_ascii=False, indent=2)
    except TypeError:
        return str(data)


def _load_attitude_config() -> dict[str, str]:
    raw = os.getenv("MARS_ATTITUDE_CONFIG_JSON", "").strip()
    if raw:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and parsed:
            return {str(k): str(v) for k, v in parsed.items()}
    return {"attitude_TNT": "Evaluate the user's sentiment towards TNT."}


async def main() -> None:
    app_root = Path(__file__).resolve().parent
    server_script = app_root / "mcp_server.py"

    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "http":
        endpoint = os.getenv("MCP_HTTP_URL", "http://localhost:8000/mcp")
        client = Client(endpoint)
        _log(f"[client] transport=http endpoint={endpoint}")
    else:
        client = Client(str(server_script))
        _log(f"[client] transport=stdio server={server_script}")

    _log("[client] call timeout=disabled heartbeat=off")

    async with client:
        runtime = await _call_tool_with_trace(
            client,
            "get_runtime_defaults",
            {},
        )
        print("== Runtime Defaults ==")
        print(_pretty(runtime))

        import_profile_path = os.getenv("MARS_IMPORT_PROFILE_CSV", "").strip()
        if import_profile_path:
            imported = await _call_tool_with_trace(
                client,
                "import_user_profiles",
                {"csv_file_path": import_profile_path},
            )
            print("== Import User Profiles ==")
            print(_pretty(imported))

        total_steps = max(1, int(os.getenv("MARS_TOTAL_STEPS", "2")))
        attitude_config = _load_attitude_config()
        sim_config = await _call_tool_with_trace(
            client,
            "set_simulation_config",
            {
                "total_steps": total_steps,
                "attitude_config": attitude_config,
            },
        )
        print("== Simulation Config ==")
        print(_pretty(sim_config))

        intervention_path: str | None = None
        raw_design = os.getenv("MARS_INTERVENTIONS_JSON", "").strip()
        if raw_design:
            built = await _call_tool_with_trace(
                client,
                "build_intervention_csv",
                {"interventions": json.loads(raw_design)},
            )
            print("== Build Intervention CSV ==")
            print(_pretty(built))

            built_payload = built
            if hasattr(built_payload, "data") and getattr(built_payload, "data") is not None:
                built_payload = getattr(built_payload, "data")
            if isinstance(built_payload, dict) and built_payload.get("ok"):
                intervention_path = str(built_payload.get("intervention_path") or "") or None

        if intervention_path is None:
            explicit_path = os.getenv("MARS_INTERVENTION_PATH", "").strip()
            intervention_path = explicit_path or None

        cleanup_db_path = os.getenv("MARS_DB_PATH", "").strip() or None
        cleanup_result = await _call_tool_with_trace(
            client,
            "cleanup_simulation_environment",
            {
                "db_path": cleanup_db_path,
                "dry_run": False,
            },
        )
        print("== Cleanup Simulation Environment ==")
        print(_pretty(cleanup_result))

        simulation_result = await _call_tool_with_trace(
            client,
            "run_marketing_simulation",
            {
                "model_name": "gpt-4o-mini",
                "intervention_path": intervention_path,
                "cleanup_before_run": False,
            },
        )
        print("== Simulation Result ==")
        print(_pretty(simulation_result))


if __name__ == "__main__":
    asyncio.run(main())
