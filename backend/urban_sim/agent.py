"""
AgentBase + PersonAgent

PersonAgent 每步执行三阶段：
  Phase 1 Observe  → router.ask("<observe>", readonly=True)  获取环境状态
  Phase 2 Decide   → LLM(profile + needs + memory + observation) → ActionDecision
  Phase 3 Act      → router.ask(instruction, readonly=False)  执行动作

去掉原版 mem0 长期记忆 / Plan / Emotion / TPB 复杂结构。
用 deque[str] 短期记忆 + Needs 满意度驱动 LLM 决策。
"""

import json
import logging
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .config import extract_json, get_llm_router

__all__ = ["AgentBase", "PersonAgent", "Needs", "ActionDecision"]

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────

class Needs(BaseModel):
    """需求满意度（0~1），值越低越紧迫，驱动 Agent 决策。"""
    satiety: float = Field(default=0.7, ge=0.0, le=1.0, description="饱腹感")
    energy: float = Field(default=0.8, ge=0.0, le=1.0, description="精力")
    safety: float = Field(default=0.9, ge=0.0, le=1.0, description="安全感")
    social: float = Field(default=0.6, ge=0.0, le=1.0, description="社交满足感")


# 被动衰减速率（每小时）：不依赖 LLM，每步按时长自动扣减
# satiety: 约16小时不吃饭会从1.0降到0
# energy:  约20小时不休息会从1.0降到0
# social:  约24小时不社交会从1.0降到0
# safety:  几乎不自然衰减
PASSIVE_DECAY_PER_HOUR: dict[str, float] = {
    "satiety": 0.03,   # 全天不吃从1.0降到0约需33小时，配合LLM调整约8小时触发进食
    "energy":  0.02,   # 精力衰减更慢，主要靠活动消耗
    "social":  0.02,   # 社交衰减慢，主要靠LLM根据性格调整
    "safety":  0.005,  # 安全感几乎不自然衰减
}


class ActionDecision(BaseModel):
    """Phase 2 LLM 输出的结构化决策。"""
    intention: str = Field(description="当前意图（一句话描述本步目标）")
    instruction: str = Field(
        default="",
        description=(
            "发给环境 router 的执行指令（自然语言）。"
            "若本步无需与环境交互（如只是思考）则留空。"
        ),
    )
    need_updates: dict[str, float] = Field(
        default_factory=dict,
        description="需求满意度调整量，如 {\"satiety\": -0.1, \"social\": 0.05}",
    )
    reasoning: str = Field(default="", description="决策简短理由")


# ─────────────────────────────────────────────────────────────
# AgentBase
# ─────────────────────────────────────────────────────────────

class AgentBase(ABC):
    """Agent 基类，定义最小接口。"""

    def __init__(self, id: int, profile: dict, name: Optional[str] = None):
        self._id = id
        self._profile = profile
        self._name = name or profile.get("name", f"Agent_{id}")
        self._router = None          # 由 init() 绑定
        self._llm_router, self._model_name = get_llm_router()

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def profile(self) -> dict:
        return self._profile

    async def init(self, router) -> None:
        """绑定环境 router（由 SimulationLoop 调用）。"""
        self._router = router

    @abstractmethod
    async def step(self, tick: int, t: datetime) -> str:
        """推进一步，返回本步行动描述。"""
        ...

    async def close(self) -> None:
        pass

    async def _llm_call(self, messages: list[dict]) -> str:
        """调用 LLM，返回文本内容。"""
        response = await self._llm_router.acompletion(
            model=self._model_name,
            messages=messages,
        )
        return response.choices[0].message.content or ""


# ─────────────────────────────────────────────────────────────
# PersonAgent
# ─────────────────────────────────────────────────────────────

class PersonAgent(AgentBase):
    """
    LLM 驱动的人物 Agent。

    每步执行：
      1. Observe：通过 router 感知当前状态（位置、消息等）
      2. Decide ：LLM 综合 profile/needs/记忆/观察 → ActionDecision
      3. Act    ：通过 router 执行 ActionDecision.instruction
    """

    def __init__(
        self,
        id: int,
        profile: dict,
        name: Optional[str] = None,
        memory_size: int = 10,
        needs: Optional[Needs] = None,
    ):
        super().__init__(id, profile, name)
        self._needs = needs or Needs()
        self._short_memory: deque[str] = deque(maxlen=memory_size)
        self._current_intention: str = "刚开始一天的活动"
        self._step_count: int = 0
        self._last_step_record: dict = {}

    # ── 主循环 ────────────────────────────────────────────────

    async def step(self, tick: int, t: datetime) -> str:
        assert self._router is not None, "Agent 未初始化，请先调用 init()"

        self._step_count += 1
        ctx = {"agent_id": self._id, "name": self._name}
        time_str = t.strftime("%H:%M")
        prefix = f"[{time_str}] {self._name:<10}"

        # ── Phase 1: Observe ──────────────────────────────────
        observation = await self._router.ask(
            ctx=ctx,
            instruction=(
                "Please observe and report my current state: "
                "location, movement status, and any unread messages."
            ),
            readonly=True,
        )
        logger.info(f"{prefix} [观察] {observation[:120].replace(chr(10), ' ')}")

        # ── Phase 2: Decide ───────────────────────────────────
        decision = await self._decide(observation, t, tick)
        self._current_intention = decision.intention

        needs = self._needs
        logger.info(
            f"{prefix} [决策] {decision.intention}"
            + (f" | 理由：{decision.reasoning}" if decision.reasoning else "")
        )
        logger.info(
            f"{prefix} [需求] 饱腹:{needs.satiety:.2f} "
            f"精力:{needs.energy:.2f} "
            f"安全:{needs.safety:.2f} "
            f"社交:{needs.social:.2f}"
        )

        # ── Phase 3: Act ──────────────────────────────────────
        act_result = ""
        if decision.instruction.strip():
            logger.info(f"{prefix} [执行] {decision.instruction}")
            act_result = await self._router.ask(
                ctx=ctx,
                instruction=decision.instruction,
                readonly=False,
                system_prompt=self._get_act_system_prompt(),
            )
            logger.info(f"{prefix} [结果] {act_result[:120].replace(chr(10), ' ')}")
        else:
            logger.info(f"{prefix} [执行] (无环境交互)")

        # 更新需求 & 记忆：先被动衰减，再叠加 LLM 的主动调整
        self._apply_passive_decay(tick)
        self._apply_need_updates(decision.need_updates)
        self._update_short_memory(t, decision.intention, act_result)

        # 保存本步结构化记录（供 SimulationLoop 收集）
        self._last_step_record = {
            "agent_id": self._id,
            "agent_name": self._name,
            "observation": observation,
            "intention": decision.intention,
            "reasoning": decision.reasoning,
            "instruction": decision.instruction,
            "act_result": act_result,
            "need_updates": decision.need_updates,
            "needs": self._needs.model_dump(),
        }

        summary = f"[{self._name}] {decision.intention}"
        if act_result:
            summary += f" → {act_result[:80]}"
        return summary

    # ── Phase 2 决策 ──────────────────────────────────────────

    async def _decide(self, observation: str, t: datetime, tick: int) -> ActionDecision:
        """调用 LLM 生成本步 ActionDecision。"""
        messages = [
            {"role": "system", "content": self._get_decide_system_prompt(t, tick)},
            {"role": "user", "content": self._build_decide_user(observation)},
        ]
        raw = await self._llm_call(messages)

        json_str = extract_json(raw)
        if json_str:
            try:
                return ActionDecision.model_validate_json(json_str)
            except Exception as e:
                logger.warning(f"[{self._name}] ActionDecision 解析失败：{e}\nRaw: {raw[:200]}")

        # fallback：将 LLM 原始回复作为 intention，不执行任何 action
        return ActionDecision(
            intention=raw.strip()[:100] or "思考中",
            instruction="",
            reasoning="JSON 解析失败，跳过本步行动",
        )

    # ── Prompt 构建 ───────────────────────────────────────────

    def _get_decide_system_prompt(self, t: datetime, tick: int) -> str:
        # 把 sample_posts 单独处理，其余字段拼成 profile_str
        skip_keys = {"sample_posts", "initial_needs", "bio", "user_id"}
        profile_str = "\n".join(
            f"  {k}: {v}" for k, v in self._profile.items() if k not in skip_keys
        )
        # 历史帖子（最多展示3条，保留 meta）
        sample_posts = self._profile.get("sample_posts", [])
        if sample_posts:
            posts_lines = []
            for p in sample_posts[:3]:
                meta = f"[{p.get('created_at','')[:10]} | {p.get('location','')}]"
                posts_lines.append(f"  {meta} {p.get('title','')}")
                if p.get("content"):
                    posts_lines.append(f"    {p['content'][:60]}")
            posts_section = "## 你的历史发帖（反映你的生活方式与兴趣）\n" + "\n".join(posts_lines) + "\n\n"
        else:
            posts_section = ""
        needs_str = (
            f"  饱腹感: {self._needs.satiety:.2f}  "
            f"精力: {self._needs.energy:.2f}  "
            f"安全感: {self._needs.safety:.2f}  "
            f"社交: {self._needs.social:.2f}"
        )
        memory_str = (
            "\n".join(f"  - {m}" for m in self._short_memory)
            if self._short_memory
            else "  （暂无记录）"
        )
        time_str = t.strftime("%Y-%m-%d %H:%M")
        tick_min = tick // 60

        return f"""你是一个生活在城市中的真实人物，当前时间是 {time_str}，本步时长 {tick_min} 分钟。

## 你的个人信息
{profile_str}

{posts_section}## 当前需求状态（0=极度匮乏，1=完全满足）
{needs_str}

## 最近行动记忆
{memory_str}

## 决策规则
- 根据当前时间、需求状态和环境观察，决定本步最合理的行动
- 需求值越低越紧迫，优先满足最迫切的需求
- 行动要符合你的性格和职业特点
- instruction 必须是可以直接传给环境执行的自然语言指令，例如：
    "移动到最近的餐厅"、"给 Alice 发消息：我在公园门口"、"前往工作地点"
- 如果暂时不需要行动（如刚到达目的地），instruction 留空

## 输出格式
必须输出合法 JSON，字段如下：
{{
  "intention": "本步意图（一句话）",
  "instruction": "环境执行指令（自然语言，或留空字符串）",
  "need_updates": {{"satiety": -0.05, "social": 0.1}},
  "reasoning": "决策理由（简短）"
}}"""

    def _build_decide_user(self, observation: str) -> str:
        return f"当前环境观察：\n{observation}\n\n请决策并输出 JSON："

    def _get_act_system_prompt(self) -> str:
        return (
            f"你在帮 {self._name} 执行环境操作。"
            "请使用可用工具完成指令，并用一句话报告执行结果。"
        )

    # ── 状态更新 ──────────────────────────────────────────────

    def _apply_need_updates(self, updates: dict[str, float]) -> None:
        for key, delta in updates.items():
            if hasattr(self._needs, key):
                current = getattr(self._needs, key)
                new_val = max(0.0, min(1.0, current + delta))
                setattr(self._needs, key, new_val)

    def _apply_passive_decay(self, tick: int) -> None:
        """按 tick 时长对所有需求施加被动衰减，与 LLM 决策无关。"""
        hours = tick / 3600.0
        for key, rate_per_hour in PASSIVE_DECAY_PER_HOUR.items():
            current = getattr(self._needs, key)
            new_val = max(0.0, current - rate_per_hour * hours)
            setattr(self._needs, key, new_val)

    def _update_short_memory(self, t: datetime, intention: str, result: str) -> None:
        time_str = t.strftime("%H:%M")
        entry = f"[{time_str}] {intention}"
        if result:
            entry += f"（{result[:60]}）"
        self._short_memory.append(entry)

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def needs(self) -> Needs:
        return self._needs

    @property
    def current_intention(self) -> str:
        return self._current_intention

    @property
    def short_memory(self) -> list[str]:
        return list(self._short_memory)

    @property
    def last_step_record(self) -> dict:
        return self._last_step_record
