from __future__ import annotations

from typing import Dict, List

from openai import OpenAI

from ..schemas.common import ModelConfig


def call_llm(model_cfg: ModelConfig, messages: List[Dict[str, str]]) -> str:
    client = OpenAI(api_key=model_cfg.api_key, base_url=model_cfg.base_url)
    response = client.chat.completions.create(
        model=model_cfg.name,
        messages=messages,
    )
    if response is None or not getattr(response, "choices", None):
        return ""
    msg = response.choices[0].message
    content = getattr(msg, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
            else:
                text = getattr(item, "text", None)
            if text:
                parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content).strip()


def call_llm_with_retry(model_cfg: ModelConfig, messages: List[Dict[str, str]], max_retries: int = 3) -> str:
    last_err = None
    for _ in range(max_retries):
        try:
            out = call_llm(model_cfg, messages)
            if out and out.strip():
                return out.strip()
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            last_err = exc
    if last_err is not None:
        raise last_err
    return ""
