import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd
from fastmcp import FastMCP


APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent


def _resolve_sim_data_dir() -> Path:
    env_override = os.getenv("MARS_SIMULATION_DIR") or os.getenv("MARS_SIM_DATA_DIR")
    if env_override:
        override_path = Path(env_override).expanduser()
        if override_path.exists():
            return override_path.resolve()

    direct_candidate = PROJECT_ROOT / "marketing_simulation" / "simulation"
    if (direct_candidate / "oasis_test_grouping.py").exists():
        return direct_candidate.resolve()

    return direct_candidate.resolve()


def _resolve_data_root() -> Path:
    configured = os.getenv("MARS_DATA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (PROJECT_ROOT / "marketing_simulation" / "data").resolve()


SIM_DATA_DIR = _resolve_sim_data_dir()
DATA_ROOT = _resolve_data_root()
SIM_SCRIPT = SIM_DATA_DIR / "oasis_test_grouping.py"
INTERVENTION_STORAGE_DIR = SIM_DATA_DIR / "interventions"
LOG_OUTPUT_DIR = SIM_DATA_DIR / "log"
MODEL_PROBE_TIMEOUT_SECONDS = 40


def _trace(message: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [mcp_server] {message}", flush=True, file=sys.stderr)


def _iter_process_snapshot() -> list[dict[str, Any]]:
    cmd = ["ps", "-eo", "pid=,ppid=,pgid=,args="]
    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        pid_raw, ppid_raw, pgid_raw, args = parts
        try:
            rows.append(
                {
                    "pid": int(pid_raw),
                    "ppid": int(ppid_raw),
                    "pgid": int(pgid_raw),
                    "args": args,
                }
            )
        except ValueError:
            continue
    return rows


def _find_simulation_processes() -> list[dict[str, Any]]:
    script_name = SIM_SCRIPT.name
    script_full = str(SIM_SCRIPT)
    current_pid = os.getpid()
    results: list[dict[str, Any]] = []
    for row in _iter_process_snapshot():
        args = row.get("args", "")
        if row.get("pid") == current_pid:
            continue
        if "mcp_server.py" in args:
            continue
        if script_name in args or script_full in args:
            results.append(row)
    return results


def _terminate_process_group(pgid: int, grace_seconds: float = 3.0) -> dict[str, Any]:
    report: dict[str, Any] = {"pgid": pgid, "terminated": False, "killed": False, "errors": []}
    if pgid <= 1:
        report["errors"].append("invalid_pgid")
        return report

    try:
        os.killpg(pgid, signal.SIGTERM)
        report["terminated"] = True
    except ProcessLookupError:
        return report
    except Exception as exc:
        report["errors"].append(f"term_failed:{exc}")

    deadline = time.time() + max(0.1, grace_seconds)
    while time.time() < deadline:
        if not any(proc.get("pgid") == pgid for proc in _iter_process_snapshot()):
            return report
        time.sleep(0.1)

    try:
        os.killpg(pgid, signal.SIGKILL)
        report["killed"] = True
    except ProcessLookupError:
        return report
    except Exception as exc:
        report["errors"].append(f"kill_failed:{exc}")
    return report


def _cleanup_runtime_state(db_path: Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    matched = _find_simulation_processes()
    pgids = sorted({int(item.get("pgid", 0)) for item in matched if int(item.get("pgid", 0)) > 1})

    cleanup_reports: list[dict[str, Any]] = []
    if not dry_run:
        for pgid in pgids:
            cleanup_reports.append(_terminate_process_group(pgid))

    sqlite_sidecar_removed: list[str] = []
    sqlite_sidecar_errors: list[str] = []
    db_target = db_path or DEFAULT_DB_PATH
    sidecars = [db_target.with_suffix(db_target.suffix + ext) for ext in ["-wal", "-shm", "-journal"]]
    for candidate in sidecars:
        if not candidate.exists():
            continue
        if dry_run:
            sqlite_sidecar_removed.append(str(candidate))
            continue
        try:
            candidate.unlink()
            sqlite_sidecar_removed.append(str(candidate))
        except Exception as exc:
            sqlite_sidecar_errors.append(f"{candidate}: {exc}")

    return {
        "ok": True,
        "dry_run": dry_run,
        "matched_processes": matched,
        "matched_groups": pgids,
        "cleanup_reports": cleanup_reports,
        "sqlite_sidecar_removed": sqlite_sidecar_removed,
        "sqlite_sidecar_errors": sqlite_sidecar_errors,
    }


def _resolve_path_from_env(env_key: str, fallback: Path) -> Path:
    override = os.getenv(env_key)
    if override:
        return Path(override).expanduser()
    return fallback


def _prefer_primary_file(file_name: str, primary_dir: Path, secondary_dir: Path) -> Path:
    primary_candidate = primary_dir / file_name
    if primary_candidate.exists():
        return primary_candidate
    secondary_candidate = secondary_dir / file_name
    if secondary_candidate.exists():
        return secondary_candidate
    return primary_candidate


DEFAULT_PROFILE_PATH = _resolve_path_from_env(
    "MARS_PROFILE_PATH",
    _prefer_primary_file("oasis_agent_init.csv", DATA_ROOT, SIM_DATA_DIR),
)
DEFAULT_DB_PATH = _resolve_path_from_env(
    "MARS_DB_PATH",
    _prefer_primary_file("oasis_database.db", DATA_ROOT, SIM_DATA_DIR),
)
DEFAULT_INTERVENTION_PATH = _resolve_path_from_env(
    "MARS_INTERVENTION_PATH",
    _prefer_primary_file("intervention_messages.csv", SIM_DATA_DIR, DATA_ROOT),
)
SIM_ENV_FILE = _resolve_path_from_env(
    "MARS_ENV_FILE",
    _prefer_primary_file(".env", DATA_ROOT, SIM_DATA_DIR),
)

DEFAULT_ATTITUDE_CONFIG = {
    "attitude_TNT": "Evaluate the user's sentiment towards TNT.",
}

INTERVENTION_COLUMNS = ["strategy_id", "target_scope", "action_type", "payload", "step"]
INTERVENTION_EXPORT_COLUMNS = [
    "time_step",
    "intervention_type",
    "content",
    "target_group",
    "target_id",
    "ratio",
    "attitude_target",
    "user_profile",
    "strategy_id",
]

ACTION_TYPE_MAP = {
    "broadcast": "broadcast",
    "bribe": "bribery",
    "bribery": "bribery",
    "register": "register_user",
    "register_user": "register_user",
}


def _read_env_file(path: Path) -> dict[str, str]:
    env_data: dict[str, str] = {}
    if not path.exists():
        return env_data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            env_data[key] = value
    return env_data


def _persist_env_file(path: Path, updates: dict[str, str]) -> None:
    existing = _read_env_file(path)
    mutated = False
    for key, raw_value in updates.items():
        value = raw_value.strip()
        if value:
            if existing.get(key) != value:
                existing[key] = value
                mutated = True
        else:
            if key in existing:
                existing.pop(key)
                mutated = True
    if not mutated:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fout:
        for key in sorted(existing.keys()):
            fout.write(f"{key}={existing[key]}\n")


def _path_to_display(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _normalize_intervention_type(raw_type: str) -> str:
    key = (raw_type or "").strip().lower()
    return ACTION_TYPE_MAP.get(key, key or "broadcast")


def _parse_target_scope(scope: str) -> tuple[str, str, str]:
    scope = (scope or "").strip()
    if not scope:
        return "", "", ""
    tokens = re.split(r"[|;,]", scope)
    target_group = ""
    target_id = ""
    ratio = ""
    for token in tokens:
        item = token.strip()
        if not item:
            continue
        if ":" in item:
            key, value = item.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"group", "target_group"}:
                target_group = value
            elif key in {"agent", "target", "target_id", "id"}:
                target_id = value.lstrip("@")
            elif key == "ratio":
                ratio = value
        else:
            if item.startswith("@") or item.isdigit():
                target_id = item.lstrip("@")
            else:
                target_group = item
    return target_group, target_id, ratio


def _build_intervention_export(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=INTERVENTION_EXPORT_COLUMNS)

    rows: list[dict[str, Any]] = []
    for record in df.to_dict("records"):
        target_group, target_id, ratio = _parse_target_scope(str(record.get("target_scope", "") or ""))
        payload = str(record.get("payload", "") or "").strip()
        normalized_type = _normalize_intervention_type(str(record.get("action_type", "") or ""))
        try:
            time_step = int(record.get("time_step") or record.get("step", 0))
        except (TypeError, ValueError):
            time_step = 0

        rows.append(
            {
                "time_step": time_step,
                "intervention_type": normalized_type,
                "content": payload,
                "target_group": target_group,
                "target_id": target_id,
                "ratio": ratio,
                "attitude_target": "",
                "user_profile": payload if normalized_type == "register_user" else "",
                "strategy_id": record.get("strategy_id", ""),
            }
        )

    return pd.DataFrame(rows, columns=INTERVENTION_EXPORT_COLUMNS)


def _run_simulation(env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_overrides)
    python_exec = env.get("OASIS_PYTHON_BIN", sys.executable)
    
    # 增加一层保险，如果获取失败，默认使用系统现有的 python3
    if not python_exec or not Path(python_exec).exists():
        python_exec = "python3"
    cmd = [python_exec, str(SIM_SCRIPT)]
    process = subprocess.Popen(
        cmd,
        cwd=WORKSPACE_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )

    stdout, stderr = process.communicate()
    return_code = process.returncode

    try:
        pgid = os.getpgid(process.pid)
    except Exception:
        pgid = -1

    if pgid > 1:
        leftovers = [item for item in _iter_process_snapshot() if int(item.get("pgid", 0)) == pgid]
        if leftovers:
            _trace(f"detected lingering processes in pgid={pgid}, forcing cleanup")
            _terminate_process_group(pgid)

    return subprocess.CompletedProcess(
        args=cmd,
        returncode=return_code,
        stdout=stdout,
        stderr=stderr,
    )


def _save_run_log(stdout: str, stderr: str) -> Path:
    LOG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_target = LOG_OUTPUT_DIR / f"mcp_run_{int(time.time())}.log"
    with open(log_target, "w", encoding="utf-8") as log_file:
        log_file.write("=== STDOUT ===\n")
        log_file.write(stdout or "")
        log_file.write("\n\n=== STDERR ===\n")
        log_file.write(stderr or "")
    return log_target


def _probe_chat_completion(
    model_base_url: str,
    model_api_key: str,
    model_name: str,
) -> dict[str, Any]:
    endpoint = f"{model_base_url.rstrip('/')}/chat/completions"
    _trace(f"model probe start endpoint={endpoint} model={model_name}")
    probe_start = time.perf_counter()
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "ping"}],
        "temperature": 0,
        "max_tokens": 16,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model_api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=MODEL_PROBE_TIMEOUT_SECONDS) as response:
            response_bytes = response.read()
            status_code = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        response_bytes = exc.read()
        status_code = exc.code
        elapsed = time.perf_counter() - probe_start
        _trace(f"model probe http error status={status_code} elapsed={elapsed:.2f}s")
    except Exception as exc:
        elapsed = time.perf_counter() - probe_start
        _trace(f"model probe exception elapsed={elapsed:.2f}s error={exc}")
        return {
            "ok": False,
            "status_code": None,
            "error": str(exc),
            "object": None,
            "response_preview": "",
        }

    raw_text = response_bytes.decode("utf-8", errors="replace")
    preview = raw_text[-4000:]
    parsed: Any = None
    parse_error = ""
    try:
        parsed = json.loads(raw_text)
    except Exception as exc:
        parse_error = str(exc)

    object_type = parsed.get("object") if isinstance(parsed, dict) else None
    error_payload = parsed.get("error") if isinstance(parsed, dict) else None
    is_chat_completion = status_code < 400 and object_type == "chat.completion"
    if parse_error and status_code < 400:
        is_chat_completion = False

    elapsed = time.perf_counter() - probe_start
    _trace(
        f"model probe done status={status_code} object={object_type} ok={is_chat_completion} elapsed={elapsed:.2f}s"
    )

    return {
        "ok": is_chat_completion,
        "status_code": status_code,
        "object": object_type,
        "error": error_payload,
        "json_parse_error": parse_error,
        "response_preview": preview,
        "endpoint": endpoint,
    }


def _save_model_probe_log(probe_result: dict[str, Any]) -> Path:
    LOG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_target = LOG_OUTPUT_DIR / f"mcp_model_probe_{int(time.time())}.log"
    with open(log_target, "w", encoding="utf-8") as log_file:
        log_file.write("=== MODEL PROBE RESULT ===\n")
        log_file.write(json.dumps(probe_result, ensure_ascii=False, indent=2))
        log_file.write("\n")
    return log_target


mcp = FastMCP("MARS Marketing Simulation MCP")


# ==========================================
# 工具区 0: 基础设施与诊断
# ==========================================

@mcp.tool
def get_runtime_defaults() -> dict[str, Any]:
    """返回当前 MCP 服务解析后的默认路径与环境状态。"""
    env_defaults = _read_env_file(SIM_ENV_FILE)
    return {
        "workspace_root": _path_to_display(WORKSPACE_ROOT),
        "simulation_dir": _path_to_display(SIM_DATA_DIR),
        "simulation_script": _path_to_display(SIM_SCRIPT),
        "data_root": _path_to_display(DATA_ROOT),
        "default_profile_path": str(DEFAULT_PROFILE_PATH),
        "default_db_path": str(DEFAULT_DB_PATH),
        "default_intervention_path": str(DEFAULT_INTERVENTION_PATH),
        "env_file": str(SIM_ENV_FILE),
        "model_base_url": env_defaults.get("MARS_MODEL_BASE_URL", os.getenv("MARS_MODEL_BASE_URL", "")),
        "model_api_key_set": bool(env_defaults.get("MARS_MODEL_API_KEY", os.getenv("MARS_MODEL_API_KEY", ""))),
        "sim_script_exists": SIM_SCRIPT.exists(),
    }


@mcp.tool
def save_model_endpoint(model_base_url: str, model_api_key: str) -> dict[str, Any]:
    """保存模型 API 配置到 .env 文件。"""
    base_url = (model_base_url or "").strip()
    api_key = (model_api_key or "").strip()
    if not base_url or not api_key:
        return {"ok": False, "error": "model_base_url 和 model_api_key 不能为空"}
    _persist_env_file(
        SIM_ENV_FILE,
        {
            "MARS_MODEL_BASE_URL": base_url,
            "MARS_MODEL_API_KEY": api_key,
        },
    )
    return {"ok": True, "env_file": str(SIM_ENV_FILE)}


@mcp.tool
def cleanup_simulation_environment(
    db_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """清理遗留模拟进程和 SQLite sidecar 文件，建议在启动新模拟前调用。"""
    resolved_db = Path(db_path).expanduser() if db_path else DEFAULT_DB_PATH
    report = _cleanup_runtime_state(db_path=resolved_db, dry_run=bool(dry_run))
    report.update(
        {
            "db_path": str(resolved_db),
            "message": "模拟环境清理完成" if not dry_run else "模拟环境清理预览完成",
        }
    )
    return report


# ==========================================
# 工具区 1-4: 标准模拟工作流管道
# ==========================================

@mcp.tool
def import_user_profiles(csv_file_path: str) -> dict[str, Any]:
    """
    [步骤 1] 导入外部的用户画像/节点数据 CSV 文件。
    如果用户提供了外部的 agent 数据，请先调用此接口导入。
    """
    source_path = Path(csv_file_path).expanduser()
    if not source_path.exists():
        return {"ok": False, "error": f"找不到文件: {source_path}"}
    
    try:
        df = pd.read_csv(source_path)
        if df.empty:
            return {"ok": False, "error": "CSV 文件为空"}
        
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        target_path = DATA_ROOT / f"custom_profiles_{int(time.time())}.csv"
        df.to_csv(target_path, index=False)
        
        _persist_env_file(SIM_ENV_FILE, {"MARS_PROFILE_PATH": str(target_path)})
        
        return {
            "ok": True, 
            "message": "用户数据导入成功，已设为模拟上下文。",
            "profile_path": str(target_path),
            "rows_imported": len(df),
            "columns": list(df.columns)
        }
    except Exception as e:
        return {"ok": False, "error": f"解析或复制 CSV 失败: {str(e)}"}


@mcp.tool
def set_simulation_config(total_steps: int, attitude_config: dict[str, str]) -> dict[str, Any]:
    """
    [步骤 2] 设置模拟的全局参数（步数和观测指标）。
    此操作应在设计干预和运行模拟之前进行。
    """
    if not isinstance(attitude_config, dict) or not attitude_config:
        return {"ok": False, "error": "attitude_config 必须是一个非空的字典 (例如 {'attitude_TNT': '描述'})"}
    
    steps = max(1, int(total_steps))
    attitude_json = json.dumps(attitude_config, ensure_ascii=False)
    
    _persist_env_file(SIM_ENV_FILE, {
        "MARS_TOTAL_STEPS": str(steps),
        "MARS_ATTITUDE_CONFIG_JSON": attitude_json
    })
    
    return {
        "ok": True,
        "message": "模拟全局配置已保存。",
        "total_steps": steps,
        "attitude_keys": list(attitude_config.keys())
    }


@mcp.tool
def build_intervention_csv(interventions: list[dict[str, Any]]) -> dict[str, Any]:
    """
    [步骤 3] 设计干预策略。将前端风格干预记录转换为 OASIS 可用 CSV 并落盘。
    """
    if not interventions:
        return {"ok": False, "error": "interventions 不能为空"}

    source_df = pd.DataFrame(interventions)
    missing = [name for name in INTERVENTION_COLUMNS if name not in source_df.columns]
    if missing:
        return {"ok": False, "error": f"缺少字段: {', '.join(missing)}"}

    cleaned = source_df[INTERVENTION_COLUMNS].copy().dropna(how="all")
    cleaned = cleaned[cleaned["strategy_id"].notnull() & cleaned["action_type"].notnull()]
    if cleaned.empty:
        return {"ok": False, "error": "清洗后无有效干预记录"}
    cleaned["step"] = cleaned["step"].fillna(0).astype(int)

    export_df = _build_intervention_export(cleaned)
    INTERVENTION_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    target = INTERVENTION_STORAGE_DIR / f"intervention_designer_{int(time.time())}.csv"
    export_df.to_csv(target, index=False)
    
    return {
        "ok": True,
        "intervention_path": str(target),
        "rows": int(len(export_df)),
    }


@mcp.tool
def run_marketing_simulation(
    intervention_path: str | None = None,
    model_name: str = "gpt-4o-mini",
    cleanup_before_run: bool = True,
) -> dict[str, Any]:
    """
    [步骤 4] 执行 OASIS 营销模拟。
    在执行前，必须确保已生成干预文件 (intervention_path) 并设置好全局配置。
    """
    run_start = time.perf_counter()
    _trace("run_marketing_simulation start")

    if not SIM_SCRIPT.exists():
        _trace(f"run_marketing_simulation abort: script missing path={SIM_SCRIPT}")
        return {"ok": False, "error": f"未找到模拟脚本: {SIM_SCRIPT}"}

    _trace("step 0/5: cleanup stale runtime state")
    cleanup_report = _cleanup_runtime_state(dry_run=not cleanup_before_run)

    _trace("step 1/5: load runtime env defaults")
    env_defaults = _read_env_file(SIM_ENV_FILE)
    resolved_base_url = env_defaults.get("MARS_MODEL_BASE_URL", os.getenv("MARS_MODEL_BASE_URL", "")).strip()
    resolved_api_key = env_defaults.get("MARS_MODEL_API_KEY", os.getenv("MARS_MODEL_API_KEY", "")).strip()

    if not resolved_base_url or not resolved_api_key:
        _trace("run_marketing_simulation abort: missing model endpoint or api key")
        return {"ok": False, "error": "缺少模型服务配置，请先调用 save_model_endpoint 设置"}

    _trace("step 2/5: resolve simulation inputs")
    resolved_total_steps = env_defaults.get("MARS_TOTAL_STEPS", "2")
    resolved_attitude_json = env_defaults.get("MARS_ATTITUDE_CONFIG_JSON", json.dumps(DEFAULT_ATTITUDE_CONFIG, ensure_ascii=False))
    resolved_profile = env_defaults.get("MARS_PROFILE_PATH", str(DEFAULT_PROFILE_PATH))
    resolved_db = Path(env_defaults.get("MARS_DB_PATH", str(DEFAULT_DB_PATH))).expanduser()
    resolved_intervention = Path(intervention_path).expanduser() if intervention_path else DEFAULT_INTERVENTION_PATH
    resolved_model_name = (model_name or "").strip() or "gpt-4o-mini"
    _trace(
        "resolved inputs "
        f"steps={resolved_total_steps} profile={resolved_profile} "
        f"intervention={resolved_intervention} db={resolved_db} model={resolved_model_name}"
    )

    _trace("step 3/5: probe model chat completion")
    probe_result = _probe_chat_completion(
        model_base_url=resolved_base_url,
        model_api_key=resolved_api_key,
        model_name=resolved_model_name,
    )
    if not probe_result.get("ok", False):
        probe_log = _save_model_probe_log(probe_result)
        elapsed = time.perf_counter() - run_start
        _trace(f"run_marketing_simulation abort: model probe failed elapsed={elapsed:.2f}s log={probe_log}")
        return {
            "ok": False,
            "error": "模型预检失败：请检查模型服务状态、额度或鉴权。",
            "log_path": str(probe_log),
            "pre_cleanup": cleanup_report,
        }

    overrides = {
        "MARS_PROFILE_PATH": str(resolved_profile),
        "MARS_DB_PATH": str(resolved_db),
        "MARS_INTERVENTION_PATH": str(resolved_intervention),
        "MARS_TOTAL_STEPS": str(resolved_total_steps),
        "MARS_ATTITUDE_CONFIG_JSON": resolved_attitude_json,
        "MARS_MODEL_NAME": resolved_model_name,
        "MARS_MODEL_BASE_URL": resolved_base_url,
        "MARS_MODEL_API_KEY": resolved_api_key,
    }

    _trace("step 4/5: launch simulation subprocess")
    sim_start = time.perf_counter()
    result = _run_simulation(overrides)
    sim_elapsed = time.perf_counter() - sim_start
    _trace(f"simulation subprocess finished return_code={result.returncode} elapsed={sim_elapsed:.2f}s")

    _trace("step 5/5: persist run log")
    log_target = _save_run_log(result.stdout or "", result.stderr or "")
    total_elapsed = time.perf_counter() - run_start
    _trace(f"run_marketing_simulation done ok={result.returncode == 0} total_elapsed={total_elapsed:.2f}s log={log_target}")

    return {
        "ok": result.returncode == 0,
        "return_code": result.returncode,
        "db_path": str(resolved_db),
        "log_path": str(log_target),
        "pre_cleanup": cleanup_report,
        "stdout_preview": (result.stdout or "")[-4000:],
        "stderr_preview": (result.stderr or "")[-4000:],
    }


# ==========================================
# 工具区 5: 数据洞察与查询
# ==========================================

@mcp.tool
def read_run_log(log_path: str, tail_lines: int = 120) -> dict[str, Any]:
    """读取某次模拟日志（尾部行）。"""
    path = Path(log_path).expanduser()
    if not path.exists():
        return {"ok": False, "error": f"日志不存在: {path}"}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    n = max(1, int(tail_lines))
    return {
        "ok": True,
        "log_path": str(path),
        "tail": "\n".join(lines[-n:]),
    }


@mcp.tool
def list_db_tables(db_path: str | None = None) -> dict[str, Any]:
    """列出数据库中的所有表名。"""
    resolved_db = Path(db_path).expanduser() if db_path else DEFAULT_DB_PATH
    if not resolved_db.exists():
        return {"ok": False, "error": f"数据库不存在: {resolved_db}"}

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(resolved_db)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        tables = [row[0] for row in rows]
        return {"ok": True, "db_path": str(resolved_db), "tables": tables}
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if conn is not None:
            conn.close()


@mcp.tool
def query_db_table(db_path: str, table_name: str, limit: int = 50) -> dict[str, Any]:
    """读取指定表的最新记录（按 rowid 倒序）。"""
    resolved_db = Path(db_path).expanduser()
    if not resolved_db.exists():
        return {"ok": False, "error": f"数据库不存在: {resolved_db}"}

    safe_table = (table_name or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", safe_table):
        return {"ok": False, "error": "table_name 不合法"}

    rows_limit = max(1, min(int(limit), 500))
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(resolved_db)
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (safe_table,),
        ).fetchone()
        if not table_exists:
            return {"ok": False, "error": f"表不存在: {safe_table}"}

        df = pd.read_sql_query(
            f"SELECT * FROM {safe_table} ORDER BY rowid DESC LIMIT ?",
            conn,
            params=(rows_limit,),
        )
        records = json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso"))
        return {
            "ok": True,
            "db_path": str(resolved_db),
            "table": safe_table,
            "rows": len(records),
            "records": records,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if conn is not None:
            conn.close()


@mcp.tool
def get_latest_posts(db_path: str | None = None, limit: int = 20) -> dict[str, Any]:
    """读取 post 表的最新帖子。"""
    resolved_db = Path(db_path).expanduser() if db_path else DEFAULT_DB_PATH
    if not resolved_db.exists():
        return {"ok": False, "error": f"数据库不存在: {resolved_db}"}

    rows_limit = max(1, min(int(limit), 200))
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(resolved_db)
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='post'").fetchone()
        if not exists:
            return {"ok": False, "error": "post 表不存在"}

        post_cols_info = pd.read_sql_query("PRAGMA table_info(post)", conn)
        post_cols = post_cols_info["name"].tolist()
        preferred_cols = ["post_id", "agent_id", "user_id", "created_at", "content", "text"]
        select_cols = [col for col in preferred_cols if col in post_cols]
        select_clause = ", ".join(select_cols) if select_cols else "*"
        order_clause = "ORDER BY datetime(created_at) DESC" if "created_at" in post_cols else "ORDER BY rowid DESC"

        df = pd.read_sql_query(
            f"SELECT {select_clause} FROM post {order_clause} LIMIT ?",
            conn,
            params=(rows_limit,),
        )
        records = json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso"))
        return {
            "ok": True,
            "db_path": str(resolved_db),
            "rows": len(records),
            "records": records,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)