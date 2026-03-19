"""
ReActRouter：Agent 与环境模块之间的调度层

Agent 发出自然语言指令 → LLM function calling 选择工具 → 执行工具 → 返回结果
精简版：去掉 set_status 特殊工具、generate_final_answer、execution_log 等复杂机制。
"""

import asyncio
import inspect
import json
import logging
from datetime import datetime
from typing import Any, Optional

from .config import get_llm_router
from .tool import EnvBase, ToolInfo

__all__ = ["ReActRouter"]

logger = logging.getLogger(__name__)


class ReActRouter:
    """
    轻量版 ReActRouter。

    工作流程（每次 ask() 调用）：
    1. 构建包含指令的 user message
    2. 调用 litellm router.acompletion(tools=...)
    3. 若响应包含 tool_calls → 执行工具 → 追加结果 → 继续循环
    4. 若响应无 tool_calls（或达到 max_steps）→ 返回最终文本
    """

    def __init__(
        self,
        env_modules: list[EnvBase],
        max_steps: int = 8,
    ):
        self.env_modules = env_modules
        self.max_steps = max_steps

        self._llm_router, self._model_name = get_llm_router()

        # 预收集所有模块工具
        self._all_tools: list[dict] = []          # 全部工具（含写操作）
        self._readonly_tools: list[dict] = []     # 只读工具
        self._tool_name_to_info: dict[str, ToolInfo] = {}
        self._tool_name_to_module: dict[str, EnvBase] = {}

        self._collect_tools()

    # ─────────────────────────────────────────────────────────
    # 生命周期
    # ─────────────────────────────────────────────────────────

    async def init(self, start_datetime: datetime) -> None:
        """初始化所有环境模块（含启动路由服务进程）。"""
        for module in self.env_modules:
            await module.init(start_datetime)
        logger.info(f"ReActRouter 初始化完成，共 {len(self.env_modules)} 个环境模块。")

    async def step(self, tick: int, t: datetime) -> None:
        """推进所有环境模块一步（更新位置插值、清理消息等）。"""
        for module in self.env_modules:
            await module.step(tick, t)

    async def close(self) -> None:
        """关闭所有环境模块。"""
        for module in self.env_modules:
            await module.close()

    # ─────────────────────────────────────────────────────────
    # 核心：ReAct 调度
    # ─────────────────────────────────────────────────────────

    async def ask(
        self,
        ctx: dict,
        instruction: str,
        readonly: bool = False,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        ReAct 主循环。

        Args:
            ctx: Agent 上下文，如 {"agent_id": 1, "name": "Alice"}。
            instruction: 自然语言指令，如 "查询我的当前位置" 或 "给 Bob 发消息：..."。
            readonly: True 时只暴露只读工具（observe 阶段使用）。
            system_prompt: 可选的系统提示（覆盖默认）。

        Returns:
            LLM 最终的文本回复。
        """
        tools = self._readonly_tools if readonly else self._all_tools

        # 构建消息列表
        sys_content = system_prompt or self._default_system_prompt()
        messages: list[dict] = [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": self._build_user_content(ctx, instruction)},
        ]

        for step in range(self.max_steps):
            response = await self._llm_call(messages, tools=tools if tools else None)
            msg = response.choices[0].message

            # 没有工具调用 → 直接返回文本
            if not msg.tool_calls:
                return msg.content or ""

            # 将 assistant 消息（含 tool_calls）加入对话
            messages.append(msg.model_dump(exclude_none=True))

            # 执行所有工具调用
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                result = await self._execute_tool(tool_name, args, readonly)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": self._serialize_result(result),
                })

        # 达到 max_steps，做最后一次无工具调用
        messages.append({
            "role": "user",
            "content": "Please summarize what you have done and provide a final answer.",
        })
        response = await self._llm_call(messages, tools=None)
        return response.choices[0].message.content or ""

    # ─────────────────────────────────────────────────────────
    # 辅助：Agent 位置查询（不经 LLM，直接查 MobilitySpace）
    # ─────────────────────────────────────────────────────────

    async def get_agent_position(
        self, agent_id: int
    ) -> tuple[Optional[float], Optional[float]]:
        """从 MobilitySpace 直接查询 agent 坐标（lng, lat）。"""
        for module in self.env_modules:
            lng, lat = await module.get_agent_position(agent_id)
            if lng is not None:
                return lng, lat
        return None, None

    # ─────────────────────────────────────────────────────────
    # 内部方法
    # ─────────────────────────────────────────────────────────

    def _collect_tools(self) -> None:
        """收集所有环境模块的 @tool 方法，构建工具索引。"""
        for module in self.env_modules:
            for tool_name, tool_info in module._tools.items():
                self._tool_name_to_info[tool_name] = tool_info
                self._tool_name_to_module[tool_name] = module

                schema = tool_info.to_openai_schema()
                self._all_tools.append(schema)
                if tool_info.readonly:
                    self._readonly_tools.append(schema)

        logger.debug(
            f"已收集 {len(self._all_tools)} 个工具，"
            f"其中只读工具 {len(self._readonly_tools)} 个。"
        )

    async def _execute_tool(
        self, tool_name: str, args: dict, readonly_context: bool
    ) -> Any:
        """
        执行单个工具调用。

        readonly_context=True 时拒绝执行写操作工具（安全防护）。
        """
        if tool_name not in self._tool_name_to_info:
            return f"Error: unknown tool '{tool_name}'"

        info = self._tool_name_to_info[tool_name]

        if readonly_context and not info.readonly:
            return f"Error: tool '{tool_name}' is not readonly, cannot call in observe phase."

        module = self._tool_name_to_module[tool_name]
        bound_fn = info.fn.__get__(module, type(module))

        try:
            if inspect.iscoroutinefunction(info.fn):
                result = await bound_fn(**args)
            else:
                result = bound_fn(**args)
            logger.debug(f"  工具调用: {tool_name}({args}) -> {str(result)[:80]}")
            return result
        except Exception as e:
            logger.warning(f"工具 '{tool_name}' 执行出错：{e}")
            return f"Error: {e}"

    async def _llm_call(self, messages: list[dict], tools: Optional[list[dict]]) -> Any:
        """调用 litellm router，带简单重试。"""
        kwargs: dict = {
            "model": self._model_name,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        return await self._llm_router.acompletion(**kwargs)

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are an environment execution engine. "
            "Use the available tools to fulfill the user's instruction. "
            "Call tools as needed, then provide a concise summary of what was done."
        )

    @staticmethod
    def _build_user_content(ctx: dict, instruction: str) -> str:
        ctx_str = json.dumps(ctx, ensure_ascii=False)
        return f"Context: {ctx_str}\nInstruction: {instruction}"

    @staticmethod
    def _serialize_result(result: Any) -> str:
        """将工具返回值序列化为字符串。"""
        if result is None:
            return "null"
        if isinstance(result, str):
            return result
        try:
            # pydantic BaseModel
            if hasattr(result, "model_dump"):
                return json.dumps(result.model_dump(), ensure_ascii=False)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception:
            return str(result)
