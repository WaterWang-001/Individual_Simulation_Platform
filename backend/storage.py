"""
仿真结果的持久化读写
每次仿真对应 results/<sim_id>/ 目录：
  meta.json   — 参数、状态、agents 元信息
  steps.jsonl — 每行一步的完整快照
"""

import json
from pathlib import Path
from typing import Optional

from config import RESULTS_DIR


# ── 写入 ──────────────────────────────────────────────────

def save_meta(sim_id: str, meta: dict) -> None:
    sim_dir = RESULTS_DIR / sim_id
    sim_dir.mkdir(exist_ok=True)
    (sim_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def open_steps_writer(sim_id: str):
    """返回打开的步骤文件句柄，调用方负责关闭。"""
    sim_dir = RESULTS_DIR / sim_id
    sim_dir.mkdir(exist_ok=True)
    return open(sim_dir / "steps.jsonl", "w", encoding="utf-8")


# ── 读取 ──────────────────────────────────────────────────

def get_simulation_meta(sim_id: str) -> Optional[dict]:
    mp = RESULTS_DIR / sim_id / "meta.json"
    if not mp.exists():
        return None
    return json.loads(mp.read_text("utf-8"))


def get_simulation_steps(sim_id: str) -> list[dict]:
    sp = RESULTS_DIR / sim_id / "steps.jsonl"
    if not sp.exists():
        return []
    steps = []
    for line in sp.read_text("utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return steps


def list_simulations() -> list[dict]:
    """
    遍历 results/ 目录，返回所有仿真的摘要列表（按时间倒序）。
    """
    rows = []
    if not RESULTS_DIR.exists():
        return rows
    for d in sorted(RESULTS_DIR.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir():
            continue
        meta = get_simulation_meta(d.name)
        if not meta:
            continue
        rows.append({
            "sim_id":       meta.get("sim_id", d.name),
            "status":       meta.get("status", "unknown"),
            "start_time":   meta.get("start_time",  ""),
            "end_time":     meta.get("end_time",     ""),
            "total_steps":  meta.get("total_steps",  0),
            "current_step": meta.get("current_step", 0),
            "num_agents":   meta.get("params", {}).get("num_agents", 0),
            "tick_seconds": meta.get("params", {}).get("tick_seconds", 3600),
        })
    return rows
