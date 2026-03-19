"""
LLM 配置模块
- 从环境变量读取 API 参数
- 构建 litellm Router 实例
- 提供 extract_json 工具函数
"""

import json
import os
import re
from typing import Optional

from dotenv import load_dotenv
from litellm import Router

load_dotenv()

__all__ = ["get_llm_router", "extract_json"]


def get_llm_router() -> tuple[Router, str]:
    """
    从环境变量构建 litellm Router，返回 (router, model_name)。

    必须设置的环境变量：
        LLM_MODEL      模型名，如 openai/gpt-4o-mini
        LLM_API_KEY    API Key

    可选：
        LLM_API_BASE   自定义 API 地址（使用代理或本地服务时需要）
    """
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("LLM_API_KEY")
    api_base = os.environ.get("LLM_API_BASE")

    if not model:
        raise ValueError("环境变量 LLM_MODEL 未设置，请在 .env 中配置。")
    if not api_key:
        raise ValueError("环境变量 LLM_API_KEY 未设置，请在 .env 中配置。")

    # litellm model_list 格式
    deployment: dict = {
        "model_name": model,
        "litellm_params": {
            "model": model,
            "api_key": api_key,
        },
    }
    if api_base:
        deployment["litellm_params"]["api_base"] = api_base

    router = Router(
        model_list=[deployment],
        num_retries=3,
        retry_after=5,
    )
    return router, model


def extract_json(text: str) -> Optional[str]:
    """
    从 LLM 响应文本中提取 JSON 字符串。
    优先匹配 ```json ... ``` 代码块，fallback 到第一个 {...} 块。

    Returns:
        JSON 字符串，或 None（未找到时）。
    """
    # 1. 尝试匹配 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        candidate = match.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 2. 扫描第一个完整 {...} 块（通过括号深度匹配）
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidate = text[start : i + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    start = -1  # 重置，继续扫描

    return None
