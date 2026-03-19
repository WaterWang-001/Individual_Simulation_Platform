"""
@tool 装饰器 + EnvBase 基类

去掉 AgentSociety2 中对 mcp.server.fastmcp 的依赖，
改用 inspect + pydantic 自己生成 OpenAI function calling 格式的 JSON Schema。
"""

import inspect
import json
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Literal, Optional, TypeVar, get_type_hints

from pydantic import BaseModel

__all__ = ["tool", "ToolInfo", "EnvBase"]

F = TypeVar("F", bound=Callable)


# ─────────────────────────────────────────────────────────────
# ToolInfo：替代原版 mcp.Tool，自持 JSON Schema
# ─────────────────────────────────────────────────────────────

@dataclass
class ToolInfo:
    name: str
    description: str
    parameters: dict          # JSON Schema（properties + required）
    fn: Callable
    readonly: bool
    kind: Optional[str]       # "observe" | "statistics" | None

    def to_openai_schema(self) -> dict:
        """生成 OpenAI function calling 格式的工具描述。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters.get("properties", {}),
                    "required": self.parameters.get("required", []),
                },
            },
        }


# ─────────────────────────────────────────────────────────────
# JSON Schema 生成辅助
# ─────────────────────────────────────────────────────────────

# Python 基础类型 → JSON Schema type
_BASIC_TYPE_MAP: dict[Any, dict] = {
    int: {"type": "integer"},
    float: {"type": "number"},
    str: {"type": "string"},
    bool: {"type": "boolean"},
}


def _type_to_schema(annotation: Any) -> dict:
    """
    将单个 Python 类型注解转换为 JSON Schema dict。
    支持：基础类型、Optional[X]、pydantic BaseModel 子类、list/List。
    """
    import types
    import typing

    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())

    # Optional[X] → X 的 schema（忽略 None）
    if origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _type_to_schema(non_none[0])
        return {"type": "string"}  # 复杂 Union，降级为 string

    # list / List[X]
    if origin in (list, typing.List) or annotation is list:
        if args:
            return {"type": "array", "items": _type_to_schema(args[0])}
        return {"type": "array"}

    # pydantic BaseModel 子类 → 内联其 JSON Schema
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        schema = annotation.model_json_schema()
        # 去掉 $defs 层（简化嵌套）
        return schema

    # 基础类型
    if annotation in _BASIC_TYPE_MAP:
        return _BASIC_TYPE_MAP[annotation]

    # 其他（datetime 等）→ string
    return {"type": "string"}


def _build_parameters_schema(fn: Callable) -> dict:
    """
    从函数签名和类型注解构建 JSON Schema（properties + required）。
    跳过 self 和 return 参数。
    """
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}

    sig = inspect.signature(fn)
    properties: dict[str, dict] = {}
    required: list[str] = []

    # 解析 docstring 中的参数说明（Google 风格）
    doc = inspect.getdoc(fn) or ""
    param_docs = _parse_param_docs(doc)

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "return"):
            continue

        annotation = hints.get(param_name, Any)
        schema = _type_to_schema(annotation)

        # 加入参数说明
        if param_name in param_docs:
            schema = {**schema, "description": param_docs[param_name]}

        properties[param_name] = schema

        # 没有默认值 → required
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {"properties": properties, "required": required}


def _parse_param_docs(docstring: str) -> dict[str, str]:
    """从 Google 风格 docstring 中提取参数说明。"""
    result: dict[str, str] = {}
    in_args = False
    for line in docstring.splitlines():
        stripped = line.strip()
        if stripped in ("Args:", "Arguments:", "Parameters:"):
            in_args = True
            continue
        if in_args:
            if stripped == "" or (stripped.endswith(":") and not stripped.startswith(" ")):
                in_args = False
                continue
            # "param_name: description" 或 "param_name (type): description"
            match = inspect.re.match(r"(\w+)(?:\s*\([^)]*\))?\s*:\s*(.*)", stripped)
            if match:
                result[match.group(1)] = match.group(2)
    return result


# ─────────────────────────────────────────────────────────────
# @tool 装饰器
# ─────────────────────────────────────────────────────────────

def tool(
    readonly: bool,
    name: Optional[str] = None,
    description: Optional[str] = None,
    kind: Optional[Literal["observe", "statistics"]] = None,
) -> Callable[[F], F]:
    """
    将环境方法注册为可被 LLM 调用的工具。

    Args:
        readonly: 为 True 时工具不修改环境状态。kind 为 observe/statistics 时必须为 True。
        name: 工具名称，默认使用函数名。
        description: 工具描述，默认使用函数 docstring 第一段。
        kind: "observe"（观察）| "statistics"（统计）| None（普通工具）。
    """
    if kind in ("observe", "statistics") and not readonly:
        raise ValueError(
            f"kind='{kind}' 的工具必须设置 readonly=True。"
        )

    def decorator(fn: F) -> F:
        tool_name = name or fn.__name__
        doc = inspect.getdoc(fn) or ""
        tool_desc = description or doc.split("\n\n")[0].strip()

        parameters = _build_parameters_schema(fn)

        fn._tool_info = ToolInfo(  # type: ignore[attr-defined]
            name=tool_name,
            description=tool_desc,
            parameters=parameters,
            fn=fn,
            readonly=readonly,
            kind=kind,
        )
        return fn

    return decorator


# ─────────────────────────────────────────────────────────────
# EnvMeta + EnvBase
# ─────────────────────────────────────────────────────────────

class EnvMeta(type):
    """元类：类定义时自动扫描 @tool 标记的方法，构建工具注册表。"""

    def __new__(mcs, name: str, bases: tuple, namespace: dict):
        cls = super().__new__(mcs, name, bases, namespace)

        # 收集本类及所有父类的 @tool 方法（子类可覆盖）
        tools: dict[str, ToolInfo] = {}
        for klass in reversed(cls.__mro__):
            for attr_name, attr_val in vars(klass).items():
                if callable(attr_val) and hasattr(attr_val, "_tool_info"):
                    info: ToolInfo = attr_val._tool_info
                    tools[info.name] = info

        cls._tools: dict[str, ToolInfo] = tools  # type: ignore[attr-defined]
        return cls


class EnvBase(metaclass=EnvMeta):
    """
    环境模块基类。

    子类通过 @tool 装饰器注册方法，EnvMeta 自动收集为 _tools。
    ReActRouter 从 _llm_tools / _readonly_llm_tools 获取 OpenAI schema。
    """

    def __init__(self):
        self.t: Optional[datetime] = None

    # ── 工具 schema 属性 ──────────────────────────────────────

    @property
    def _llm_tools(self) -> list[dict]:
        """所有工具的 OpenAI function calling schema 列表。"""
        return [info.to_openai_schema() for info in self._tools.values()]

    @property
    def _readonly_llm_tools(self) -> list[dict]:
        """只读工具的 OpenAI schema 列表（readonly=True）。"""
        return [
            info.to_openai_schema()
            for info in self._tools.values()
            if info.readonly
        ]

    # ── 生命周期 ──────────────────────────────────────────────

    @property
    def description(self) -> str:
        """子类可覆盖，提供模块描述（用于 router 的系统提示）。"""
        return self.__class__.__name__

    async def init(self, start_datetime: datetime) -> None:
        """初始化模块（子类按需覆盖）。"""
        self.t = start_datetime

    async def step(self, tick: int, t: datetime) -> None:
        """推进一步（子类必须覆盖）。"""
        self.t = t

    async def close(self) -> None:
        """关闭/清理资源（子类按需覆盖）。"""
        pass

    async def get_agent_position(
        self, agent_id: int
    ) -> tuple[Optional[float], Optional[float]]:
        """获取 Agent 位置（仅 MobilitySpace 子类实现）。"""
        return None, None
