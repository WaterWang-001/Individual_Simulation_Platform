from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    PLUGIN_ROOT / 'benchmark_sources',
    PLUGIN_ROOT / 'benchmarks',
    PLUGIN_ROOT / 'outputs',
]
REPLACEMENTS = {
    "智能访谈项目代码/自动化问答/benchmarks/": "benchmarks/",
    "智能访谈项目代码/自动化问答/outputs/": "outputs/",
    "智能访谈项目代码/Time_management_questionnaire.jsonl": "Time_management_questionnaire.jsonl",
}


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        root = str(PLUGIN_ROOT.resolve()) + '/'
        if value.startswith(root):
            return value[len(root):]
        for old, new in REPLACEMENTS.items():
            if value.startswith(old):
                return new + value[len(old):]
    return value


def clean_json_file(path: Path) -> bool:
    original = path.read_text(encoding='utf-8')
    data = json.loads(original)
    cleaned = sanitize(data)
    new_text = json.dumps(cleaned, ensure_ascii=False, indent=2)
    if new_text != original:
        path.write_text(new_text + ('\n' if not new_text.endswith('\n') else ''), encoding='utf-8')
        return True
    return False


def clean_jsonl_file(path: Path) -> bool:
    original = path.read_text(encoding='utf-8').splitlines()
    changed = False
    lines = []
    for line in original:
        if not line.strip():
            continue
        obj = json.loads(line)
        cleaned = sanitize(obj)
        new_line = json.dumps(cleaned, ensure_ascii=False)
        if new_line != line:
            changed = True
        lines.append(new_line)
    if changed:
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return changed


def main() -> None:
    changed = []
    for target in TARGETS:
        if not target.exists():
            continue
        for path in target.rglob('*'):
            if not path.is_file():
                continue
            if path.suffix == '.json':
                if clean_json_file(path):
                    changed.append(path)
            elif path.suffix == '.jsonl':
                if clean_jsonl_file(path):
                    changed.append(path)
    print(json.dumps({
        'plugin_root': str(PLUGIN_ROOT),
        'changed_count': len(changed),
        'changed_files': [str(p.relative_to(PLUGIN_ROOT)) for p in changed[:200]],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
