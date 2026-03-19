# SetupView 修改方案

> **职责**：Step 1 — Agent 配置 + 关系图谱预览，配置完成后跳转到 SimulationView
>
> **本次改动范围**：最小改动，仅删除仿真参数区块、修改底部按钮

---

## 1. 页面定位

```
Step 1: SetupView         Step 2: SimulationView     Step 3: OnlineSimView
  配置 Agent 数量           仿真参数 + 启动 + 历史        线上环境仿真
  预览关系图谱
  [Next Step →]  ────────▶
```

SetupView **不再负责**仿真参数配置，仅完成：
- 选择 Agent 数量
- 查看 Agent 关系图谱
- 确认后跳转 SimulationView（携带 Agent 参数）

---

## 2. 当前结构（需变更部分标注）

```
SetupView
├── NavBar (step 1 active)
└── .workspace
    ├── GraphPanel (左侧，保持不变)
    └── .config-pane (右侧)
        ├── Agent Selection        ← 保持不变
        ├── Network Stats          ← 保持不变
        ├── Simulation Parameters  ← ❌ 删除整个 cfg-section
        ├── System Log             ← 保持不变
        └── [Start Simulation]     ← ✏️ 改为 [Next Step →]
```

---

## 3. 删除内容

删除 `SetupView.vue` 中的 **Simulation Parameters** `cfg-section`：

```html
<!-- 删除这整块 -->
<div class="cfg-section">
  <div class="cfg-section-title">Simulation Parameters</div>
  <!-- Steps slider -->
  <!-- Time per Step select -->
  <!-- Start Time datetime -->
  <!-- LLM Concurrency slider -->
</div>
```

同步删除对应的 `<script setup>` 中的响应式变量：
- `numSteps`
- `tickSeconds`
- `startTime`
- `concurrency`

---

## 4. 修改底部按钮

### 模板

```html
<!-- 从 -->
<button class="btn-start-sim" :disabled="loading || !allProfiles.length" @click="startSimulation">
  <svg ...><polygon points="5,3 13,8 5,13"/></svg>
  Start Simulation
</button>

<!-- 改为 -->
<button class="btn-start-sim" :disabled="loading || !allProfiles.length" @click="nextStep">
  Next Step
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M3 8h10M9 4l4 4-4 4"/>
  </svg>
</button>
```

### 逻辑

```javascript
// 原 startSimulation() 改为 nextStep()
function nextStep() {
  const params = {
    num_agents: agentCount.value,
    agent_ids:  selectedAgents.value.map(a => a.user_id),
  }
  localStorage.setItem('agentParams', JSON.stringify(params))
  log(`Selected <span class="log-info">${params.num_agents}</span> agents — proceeding to simulation config`)
  setTimeout(() => router.push('/simulation'), 300)
}
```

**注意**：不再传递 `num_steps / tick_seconds / concurrency / start_time`，这些由 SimulationView 自己维护。

---

## 5. 保持不变的内容

| 内容 | 说明 |
|------|------|
| NavBar + step indicator (step 1 active) | 不变 |
| GraphPanel 组件 | 不变 |
| Agent count slider + 分布统计 | 不变 |
| Network Stats (Agents / Connections / Avg Degree) | 不变 |
| System Log | 不变 |
| `getProfiles()` / `getRelationships()` API 调用 | 不变 |
| 所有 CSS / 样式 | 不变 |

---

## 6. localStorage 传递规范

SetupView 写入，SimulationView 读取：

```javascript
// SetupView 写入
localStorage.setItem('agentParams', JSON.stringify({
  num_agents: 10,
  agent_ids: ['uuid-001', 'uuid-002', ...]   // 当前选中的 Agent ID 列表
}))

// SimulationView 读取（start 时使用）
const agentParams = JSON.parse(localStorage.getItem('agentParams') || '{}')
// agentParams.num_agents → 传给后端的 num_agents
```

---

## 7. 改动文件

- `frontend/src/views/SetupView.vue` — 唯一改动文件
- 不涉及 router、api、组件
