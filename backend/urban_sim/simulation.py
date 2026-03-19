"""
SimulationLoop：多 Agent 并行仿真循环

- asyncio.Semaphore 控制并发数，防止 LLM API rate limit
- 支持 async with 上下文管理器
- step() 先并行推进所有 Agent，再更新环境物理状态
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import tqdm as tqdm_module

from .agent import AgentBase, PersonAgent
from .router import ReActRouter

__all__ = ["SimulationLoop"]

logger = logging.getLogger(__name__)


class SimulationLoop:
    """
    管理多个 Agent 的并行仿真循环。

    用法：
        async with SimulationLoop(agents, router, start_t, concurrency=5) as sim:
            await sim.run(num_steps=48, tick=300)
    """

    def __init__(
        self,
        agents: list[AgentBase],
        router: ReActRouter,
        start_t: datetime,
        concurrency: int = 5,
        output_dir: Optional[str] = None,
    ):
        """
        Args:
            agents: Agent 列表。
            router: 环境路由器。
            start_t: 仿真起始时间。
            concurrency: 同时运行的 Agent 数量上限（用 Semaphore 控制）。
                         推荐设为 LLM API 并发限制的 1/4 到 1/2。
        """
        self._agents = agents
        self._router = router
        self._t = start_t
        self._concurrency = concurrency
        self._step_count = 0
        self._semaphore = asyncio.Semaphore(concurrency)
        self._output_dir = output_dir
        self._all_records: list[dict] = []

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def current_time(self) -> datetime:
        return self._t

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def agents(self) -> list[AgentBase]:
        return self._agents

    @property
    def router(self) -> ReActRouter:
        return self._router

    # ── 生命周期 ──────────────────────────────────────────────

    async def init(self) -> None:
        """
        初始化：
        1. 启动所有环境模块（含路由服务进程）
        2. 绑定每个 Agent 的 router
        """
        await self._router.init(self._t)
        for agent in self._agents:
            await agent.init(self._router)
        logger.info(
            f"SimulationLoop 初始化完成。"
            f"Agent 数: {len(self._agents)}，并发数: {self._concurrency}"
        )

    async def close(self) -> None:
        """关闭所有 Agent 和环境模块。"""
        for agent in self._agents:
            await agent.close()
        await self._router.close()
        logger.info("SimulationLoop 已关闭。")

    async def __aenter__(self) -> "SimulationLoop":
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _save_results(self) -> None:
        """将仿真记录写入 JSONL 和 summary JSON 文件。"""
        if not self._output_dir or not self._all_records:
            return

        os.makedirs(self._output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 详细记录：每人每步一行 JSONL
        detail_path = os.path.join(self._output_dir, f"simulation_{timestamp}.jsonl")
        with open(detail_path, "w", encoding="utf-8") as f:
            for record in self._all_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 汇总：每人的轨迹点和访问地点
        summary: dict = {}
        for record in self._all_records:
            aid = record["agent_id"]
            if aid not in summary:
                summary[aid] = {
                    "agent_id": aid,
                    "agent_name": record["agent_name"],
                    "steps": [],
                }
            summary[aid]["steps"].append({
                "step": record["step"],
                "sim_time": record["sim_time"],
                "intention": record["intention"],
                "act_result": record["act_result"],
                "needs": record["needs"],
                "position": record["position"],
            })

        summary_path = os.path.join(self._output_dir, f"simulation_{timestamp}_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(list(summary.values()), f, ensure_ascii=False, indent=2)

        logger.info(f"仿真结果已保存：\n  详细记录 -> {detail_path}\n  汇总     -> {summary_path}")

    # ── 步进 ──────────────────────────────────────────────────

    async def step(self, tick: int) -> list[str]:
        """
        推进一步。

        流程：
          1. 时间前进 tick 秒
          2. 所有 Agent 并行执行（受 Semaphore 控制并发数）
          3. 环境模块更新物理状态（位置插值、消息清理等）

        Args:
            tick: 本步时长（秒）。

        Returns:
            每个 Agent 本步行动描述列表。
        """
        self._t += timedelta(seconds=tick)

        done_count = 0
        agent_bar = tqdm_module.tqdm(
            total=len(self._agents),
            desc=f"  Step {self._step_count + 1} agents",
            leave=False,
            ncols=80,
        )

        async def _run_agent(agent: AgentBase) -> str:
            nonlocal done_count
            async with self._semaphore:
                try:
                    result = await agent.step(tick, self._t)
                except Exception as e:
                    logger.error(f"Agent {agent.name}(id={agent.id}) step 出错: {e}")
                    result = f"[{agent.name}] ERROR: {e}"
            done_count += 1
            agent_bar.update(1)
            return result

        results = await asyncio.gather(*[_run_agent(a) for a in self._agents])
        agent_bar.close()

        await self._router.step(tick, self._t)
        self._step_count += 1

        return list(results)

    async def run(
        self,
        num_steps: int,
        tick: int,
        on_step_end: Optional[callable] = None,
    ) -> None:
        """
        运行指定步数。

        Args:
            num_steps: 总步数。
            tick: 每步时长（秒）。
            on_step_end: 可选回调，签名 async def on_step_end(sim, step, results)。
        """
        step_bar = tqdm_module.tqdm(
            total=num_steps,
            desc="Simulation",
            ncols=80,
            unit="step",
        )
        for i in range(num_steps):
            results = await self.step(tick)

            time_str = self._t.strftime("%H:%M")
            step_bar.set_postfix({"time": time_str})
            step_bar.update(1)
            logger.info(f"Step {self._step_count:4d} | {time_str} | {len(results)} agents done")

            # 收集本步所有 agent 的记录
            for agent in self._agents:
                if isinstance(agent, PersonAgent) and agent.last_step_record:
                    record = dict(agent.last_step_record)
                    record["step"] = self._step_count
                    record["sim_time"] = time_str
                    # 查询当前经纬度位置
                    lng, lat = await self._router.get_agent_position(agent.id)
                    record["position"] = {"lng": lng, "lat": lat}
                    self._all_records.append(record)

            if on_step_end is not None:
                await on_step_end(self, self._step_count, results)

        step_bar.close()
        self._save_results()
