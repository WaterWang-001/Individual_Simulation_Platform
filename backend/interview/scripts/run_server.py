from __future__ import annotations

import json
import sys
from importlib.util import find_spec
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from config import load_plugin_config, project_model_config_candidates, resolve_config_secret


def _preflight_runtime() -> int:
    if find_spec("fastmcp") is None:
        print("启动失败: 缺少依赖 fastmcp。")
        print("请先执行: pip install -r requirements.txt")
        print("如果只想验证离线回退能力，可执行: python3 scripts/smoke_test.py")
        return 1

    plugin_config = load_plugin_config(PLUGIN_ROOT)
    candidates = project_model_config_candidates(PLUGIN_ROOT, plugin_config.project_model_config)
    config_path = next((path for path in candidates if path.exists()), None)
    if config_path is None:
        checked = "、".join(str(path.relative_to(PLUGIN_ROOT)) if path.is_relative_to(PLUGIN_ROOT) else str(path) for path in candidates)
        print(f"运行提示: 未找到模型配置 {checked}。服务仍可启动，但主流程将优先使用规则回退。")
        return 0

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"运行提示: 模型配置读取失败 {config_path}: {exc}。服务仍可启动，但将退回规则模式。")
        return 0

    defaults = [plugin_config.default_interviewer, plugin_config.default_interviewee]
    found_names = {str(item.get('name')): item for item in raw.get("models", []) if isinstance(item, dict)}
    issues = []
    for model_name in defaults:
        item = found_names.get(model_name)
        if item is None:
            issues.append(f"{model_name}: 未在 {config_path.name} 中找到")
            continue
        _, key_warning = resolve_config_secret(item.get("api_key"), str(item.get("api_key_env") or ""))
        _, url_warning = resolve_config_secret(item.get("base_url"), str(item.get("base_url_env") or ""))
        if key_warning:
            issues.append(f"{model_name}: api_key {key_warning}")
        if url_warning:
            issues.append(f"{model_name}: base_url {url_warning}")
    rel_path = str(config_path.relative_to(PLUGIN_ROOT)) if config_path.is_relative_to(PLUGIN_ROOT) else str(config_path)
    if issues:
        print(f"运行提示: 已加载模型配置 {rel_path}，但默认模型不可直接联网调用。")
        for issue in issues:
            print(f"- {issue}")
        print("服务会继续启动；相关工具在运行时会自动退回规则模式。")
        return 0

    print(f"运行提示: 已加载模型配置 {rel_path}。启动前不会主动探测外网连通性。")
    return 0


if __name__ == "__main__":
    status = _preflight_runtime()
    if status != 0:
        raise SystemExit(status)
    from server import mcp

    mcp.run()
