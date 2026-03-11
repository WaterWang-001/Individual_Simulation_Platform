from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class PluginConfig:
    server_name: str = "intelligent-interview-platform"
    project_root: str = "."
    default_outputs_dir: str = "./outputs"
    default_clean_only: bool = True
    default_interviewer: str = "qwen3-max"
    default_interviewee: str = "qwen3-max"
    project_model_config: str = "./project_config.json"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server_name": self.server_name,
            "project_root": self.project_root,
            "default_outputs_dir": self.default_outputs_dir,
            "default_clean_only": self.default_clean_only,
            "project_model_config": self.project_model_config,
            "models": {
                "default_interviewer": self.default_interviewer,
                "default_interviewee": self.default_interviewee,
            },
        }


def load_plugin_config(plugin_root: Path) -> PluginConfig:
    config_path = plugin_root / "config.json"
    sample_path = plugin_root / "config.sample.json"
    raw: Dict[str, Any] = {}
    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    elif sample_path.exists():
        raw = json.loads(sample_path.read_text(encoding="utf-8"))
    models = raw.get("models", {})
    cfg = PluginConfig(
        server_name=str(raw.get("server_name", "intelligent-interview-platform")),
        project_root=str(raw.get("project_root", ".")),
        default_outputs_dir=str(raw.get("default_outputs_dir", "./outputs")),
        default_clean_only=bool(raw.get("default_clean_only", True)),
        project_model_config=str(raw.get("project_model_config", "./project_config.json")),
        default_interviewer=str(models.get("default_interviewer", "qwen3-max")),
        default_interviewee=str(models.get("default_interviewee", "qwen3-max")),
    )
    env_model_config = os.environ.get("FASTMCP_PROJECT_MODEL_CONFIG")
    if env_model_config:
        cfg.project_model_config = env_model_config
    env_outputs = os.environ.get("FASTMCP_DEFAULT_OUTPUTS_DIR")
    if env_outputs:
        cfg.default_outputs_dir = env_outputs
    env_clean = os.environ.get("FASTMCP_DEFAULT_CLEAN_ONLY")
    if env_clean is not None:
        cfg.default_clean_only = env_clean.strip().lower() in {"1", "true", "yes"}
    return cfg


def project_model_config_candidates(plugin_root: Path, configured_path: str) -> List[Path]:
    target = Path(configured_path).expanduser()
    if not target.is_absolute():
        target = (plugin_root / target).resolve()
    else:
        target = target.resolve()
    candidates: List[Path] = []
    if target.name == "project_config.json":
        candidates.append(target.with_name("project_config.local.json"))
    candidates.append(target)
    unique: List[Path] = []
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def resolve_config_secret(value: Any, env_name: str = "") -> tuple[str, str | None]:
    secret = str(value or "").strip()
    env_key = str(env_name or "").strip()
    if not env_key and secret.startswith("env:"):
        env_key = secret[4:].strip()
    elif not env_key and secret.startswith("${") and secret.endswith("}"):
        env_key = secret[2:-1].strip()
    if env_key:
        resolved = os.environ.get(env_key, "").strip()
        if not resolved:
            return "", f"环境变量 {env_key} 未设置"
        return resolved, None
    if not secret:
        return "", "缺少配置"
    if secret.startswith("YOUR_"):
        return "", "仍为模板占位值"
    return secret, None
