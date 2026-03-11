from __future__ import annotations

from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
PROMPT_DIR = BASE_DIR / "prompts"


def load_prompt(name: str, prompt_dir: Path | None = None) -> str:
    path = (prompt_dir or PROMPT_DIR) / name
    return path.read_text(encoding="utf-8")


def render_prompt(template: str, **kwargs: Any) -> str:
    return template.format(**kwargs)
