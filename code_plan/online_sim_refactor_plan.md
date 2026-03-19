# OnlineSim 重构计划（v1）

> 三项改进：① 将仿真逻辑内联进 online_sim.py；② 开启 Attitude 标注；③ 新增态度曲线解读功能

---

## 0. 当前架构回顾（问题所在）

```
online_sim.py
  └─ _run_simulation()
       └─ subprocess.Popen(oasis_test_grouping.py)   ← 跨进程，靠 stdout 解析进度
            ├─ env vars → 配置传递（MARS_* 变量）
            └─ oasis conda env 的 Python 解释器运行

问题：
  - 代码分散在两个文件，逻辑割裂
  - 进度靠正则解析 stdout，脆弱
  - Attitude 标注循环被注释，折线图无动态数据
  - 无曲线解读功能
```

---

## 1. 改进一：内联仿真逻辑（消除独立子进程脚本）

### 1.1 前提条件

Flask 必须用 oasis conda 环境的 Python 启动：

```bash
# 启动 Flask 时切换到 oasis 环境
conda activate oasis
python backend/app.py
```

或在 `backend/app.py` 顶部加路径操作（不推荐）。

### 1.2 新建 `simulation/oasis_sim.py`

将 `oasis_test_grouping.py` 的 `main()` 重构为可调用的 async 函数：

```python
# simulation/oasis_sim.py

async def run_simulation(
    profile_path: str,
    db_path: str,
    intervention_path: str,
    total_steps: int,
    model_name: str,
    model_base_url: str,
    model_api_key: str,
    attitude_config: dict,           # {metric_key: description}
    progress_callback=None,          # callable(step, total) — 替代 stdout 输出
    log_callback=None,               # callable(message: str)
) -> None:
    """
    完整的 OASIS 仿真循环，含 Attitude 标注。
    由 online_sim.py 在独立线程中通过 asyncio.run() 调用。
    """
    ...（从 oasis_test_grouping.py main() 复制并参数化）
```

关键变化：
- 全局常量 → 函数参数
- `logger.info(...)` → `log_callback(...)` + `logger.info(...)`
- `Simulation Step X / N` 输出 → `progress_callback(step, total)` 回调
- Attitude 标注取消注释（见改进二）

### 1.3 修改 `online_sim.py`

```python
# 替换 subprocess.Popen 方案
from simulation.oasis_sim import run_simulation

def _run_simulation(state, tmp_dir, body):
    ...
    def _on_progress(step, total):
        state.progress = step
        state.log_queue.put({"type": "step_done", "step": step})

    def _on_log(msg):
        state.log_queue.put({"type": "log", "message": msg})

    try:
        asyncio.run(run_simulation(
            profile_path=str(tmp_dir / "agents.csv"),
            db_path=str(tmp_dir / "oasis.db"),
            intervention_path=str(tmp_dir / "interventions.csv"),
            total_steps=body.get("total_steps", 4),
            model_name=api_cfg.get("MARS_MODEL_NAME", "deepseek-chat"),
            model_base_url=api_cfg.get("MARS_MODEL_BASE_URL", ""),
            model_api_key=api_cfg.get("MARS_MODEL_API_KEY", ""),
            attitude_config={metric_key: f"...{topic}..."},
            progress_callback=_on_progress,
            log_callback=_on_log,
        ))
        state.status = "completed"
        state.log_queue.put({"type": "complete"})
    except Exception as e:
        state.status = "error"
        state.log_queue.put({"type": "error", "message": str(e)})
    finally:
        state.log_queue.put(None)
```

### 1.4 保留 `oasis_test_grouping.py` 作 CLI 测试入口

```python
# oasis_test_grouping.py（精简为 10 行）
import asyncio, os
from simulation.oasis_sim import run_simulation

if __name__ == "__main__":
    asyncio.run(run_simulation(
        profile_path=os.getenv("MARS_PROFILE_PATH"),
        ...
    ))
```

### 1.5 改动文件

| 文件 | 操作 |
|---|---|
| `simulation/oasis_sim.py` | **新建**：提取 main() 为可调用函数 |
| `online_sim.py` | 修改 `_run_simulation`：用 asyncio.run() 替换 subprocess |
| `oasis_test_grouping.py` | 精简为 CLI 薄包装 |

---

## 2. 改进二：开启 Attitude 标注（让折线图有动态数据）

### 2.1 问题根因

`oasis_test_grouping.py` 中 Attitude 标注循环被注释掉：

```python
# 11.4 Attitude 标注
# if annotator:
#     try:
#         await annotator.annotate_table(db_path, "post", ...)
```

导致 `post` 表没有 attitude 分数，折线图无数据。

### 2.2 修改 `oasis_sim.py`（或 oasis_test_grouping.py）

**初始化标注器**（在模型初始化后）：

```python
from attitude_annotator import OpenAIAttitudeAnnotator

annotator = OpenAIAttitudeAnnotator(
    model_name=model_name,
    api_key=model_api_key,
    attitude_config=attitude_config,      # {metric_key: description}
    base_url=model_base_url,
    concurrency_limit=5,                  # deepseek 支持并发
)
```

**每步标注后聚合**（在 `await env.step()` 之后）：

```python
# 11.4 Attitude 标注
await annotator.annotate_table(
    db_path=db_path,
    table_name="post",
    only_sim_posts=True,
    batch_size=50
)
log_callback(f"Step {current_step}: 标注完成")

# 11.5 聚合写入 attitude_step_group 表（供前端折线图使用）
_aggregate_attitude_to_table(db_path, current_step, agent_map, metric_key)
```

### 2.3 新建聚合函数 `_aggregate_attitude_to_table`

```python
def _aggregate_attitude_to_table(db_path, step, agent_map, metric_col):
    """
    读取已标注的 post 表，按 step + group 聚合平均态度分，
    写入 attitude_step_group 表。

    表结构：
    CREATE TABLE attitude_step_group (
        time_step INTEGER,
        group_name TEXT,
        avg_score REAL,
        post_count INTEGER
    )
    """
    conn = sqlite3.connect(db_path)
    # 从 post 表按 user_id 聚合 → agent_map 查 group → 按 group 平均
    ...
    conn.close()
```

### 2.4 修改 `online_sim.py` 的 `get_attitude` 端点

优先读取 `attitude_step_group` 表（标注数据），fallback 原有表：

```python
# 新增：尝试 attitude_step_group 表（标注后的动态数据）
if tbl_exists("attitude_step_group"):
    rows = conn.execute(
        "SELECT time_step, group_name, avg_score FROM attitude_step_group ORDER BY time_step"
    ).fetchall()
    if rows:
        # 直接组装折线图数据并返回
        ...
```

### 2.5 改动文件

| 文件 | 操作 |
|---|---|
| `simulation/oasis_sim.py` | 取消注释标注循环；初始化 OpenAIAttitudeAnnotator；添加 `_aggregate_attitude_to_table` |
| `online_sim.py` | `get_attitude` 优先读 `attitude_step_group` 表 |

---

## 3. 改进三：态度曲线解读（LLM 分析）

### 3.1 功能描述

仿真完成后，用户点击 **"Interpret Curve"** 按钮，后端调用 deepseek 对态度曲线数据生成文字解读。

### 3.2 新增后端端点

```
POST /api/online-sim/<id>/attitude/interpret
```

请求体：无需传参（后端自行从 DB 读取）

响应：

```json
{
  "interpretation": "...(200-400字中文解读)...",
  "topic": "AuroraEV",
  "generated_at": "2026-03-18T10:30:00"
}
```

**实现逻辑**（`online_sim.py`）：

```python
@bp.route("/<sim_id>/attitude/interpret", methods=["POST"])
def interpret_attitude(sim_id):
    state = _active.get(sim_id)
    attitude_data = _load_attitude_data(state)   # 复用 get_attitude 逻辑

    prompt = _build_interpret_prompt(
        topic=state.topic,
        attitude_data=attitude_data,   # {steps, groups: {group: [scores]}}
        interventions=state.interventions,   # 干预信息作上下文
    )

    api_cfg = _load_api_config()
    result = _call_llm_sync(
        prompt=prompt,
        model=api_cfg.get("MARS_MODEL_NAME", "deepseek-chat"),
        api_key=api_cfg.get("MARS_MODEL_API_KEY"),
        base_url=api_cfg.get("MARS_MODEL_BASE_URL"),
    )
    return jsonify({"interpretation": result, "topic": state.topic, ...})
```

**Prompt 模板**：

```
你是一名社会媒体研究员，正在分析一场针对主题「{topic}」的舆情仿真结果。

模拟共进行 {total_steps} 步，包含以下群体：{group_names}。

各群体的态度变化（-1=极度负面，0=中立，+1=极度正面）如下：
{attitude_table}

{intervention_context}

请从以下角度解读这条曲线：
1. 整体趋势：舆论是向正面还是负面演化？
2. 群体差异：哪个群体最支持/最抗拒？为何？
3. 转折点：哪一步出现明显变化？可能原因是什么？
4. 干预效果（若有）：营销干预是否改变了态度走势？
5. 结论与建议：此次仿真对真实营销活动有何启示？

请用简洁、专业的中文回答，100-300字。
```

### 3.3 前端改动（OnlineSimView.vue）

在 attitude-panel 右上角添加按钮：

```html
<button @click="interpretCurve" :disabled="interpreting || !attitudeData || !simDone">
  {{ interpreting ? '解读中...' : '✦ 解读曲线' }}
</button>
```

在折线图下方显示解读卡片：

```html
<div v-if="interpretation" class="interpret-card">
  <div class="interpret-title">AI 解读</div>
  <p class="interpret-text">{{ interpretation }}</p>
</div>
```

新增状态变量：

```javascript
const interpreting   = ref(false)
const interpretation = ref('')

async function interpretCurve() {
  interpreting.value = true
  const res = await api.post(`/api/online-sim/${onlineSimId.value}/attitude/interpret`)
  interpretation.value = res.data.interpretation
  interpreting.value = false
}
```

新增 API 函数（`api/index.js`）：

```javascript
export const interpretAttitude = (id) =>
  api.post(`/api/online-sim/${id}/attitude/interpret`).then(r => r.data)
```

### 3.4 改动文件

| 文件 | 操作 |
|---|---|
| `online_sim.py` | 新增 `interpret_attitude` 路由 + `_build_interpret_prompt` + `_call_llm_sync` |
| `OnlineSimView.vue` | 新增 interpreting/interpretation 状态 + 按钮 + 解读卡片 |
| `frontend/src/api/index.js` | 新增 `interpretAttitude` 函数 |

---

## 4. 实施顺序

```
改进二（最有价值，立刻有折线图数据）
   ↓
改进三（依赖折线图数据才能解读）
   ↓
改进一（架构优化，最后做，避免引入风险）
```

---

## 5. 风险与注意事项

| 风险 | 处理方式 |
|---|---|
| 改进一要求 Flask 在 oasis conda env 下运行 | 启动命令改为 `conda activate oasis && python app.py` |
| 标注调 LLM 每步会增加仿真时间 | 可设 `MARS_ANNOTATE=false` 环境变量跳过标注 |
| `OpenAIAttitudeAnnotator` 校验 api_key 必须以 `sk-` 开头 | deepseek key 格式符合，但需确认 |
| interpret endpoint 超时（deepseek 慢） | 设 timeout=30s，前端 loading 状态 |
| 改进一中 asyncio 在已有事件循环的线程里调用 | 每次在新线程中 `asyncio.run()` 即可（Flask worker thread 无既有 loop）|
