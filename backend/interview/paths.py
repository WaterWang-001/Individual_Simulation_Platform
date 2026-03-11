from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from .config import PluginConfig
except ImportError:  # script mode
    from config import PluginConfig


@dataclass
class PluginPaths:
    plugin_root: Path
    project_root: Path
    prompts_dir: Path
    benchmarks_dir: Path
    outputs_dir: Path
    demo_root: Path
    project_model_config_path: Path


def resolve_paths(plugin_root: Path, config: PluginConfig) -> PluginPaths:
    project_root = (plugin_root / config.project_root).resolve()
    for candidate in [project_root, plugin_root]:
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
    return PluginPaths(
        plugin_root=plugin_root,
        project_root=project_root,
        prompts_dir=project_root / "prompts",
        benchmarks_dir=project_root / "benchmarks",
        outputs_dir=(plugin_root / config.default_outputs_dir).resolve(),
        demo_root=project_root / "demo_web_streamlit",
        project_model_config_path=(plugin_root / config.project_model_config).resolve(),
    )
