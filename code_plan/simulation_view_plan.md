# SimulationView 重设计方案

> **职责**：Step 2 — 配置仿真参数、启动仿真、在地图上展示 Agent 行为、查看历史仿真结果
>
> 完全重写现有 SimulationView.vue

---

## 1. 页面定位

```
Step 1: SetupView         Step 2: SimulationView              Step 3: OnlineSimView
  选 Agent → Next Step ──▶  配置参数 → Start Simulation          线上环境仿真
                             地图展示 + 历史列表
                             完成后 [Next Step →] ─────────────▶
```

---

## 2. 整体布局

```
┌──────────────────────────────────────────────────────────────────┐
│  NavBar  (step 1 done ✓ · step 2 active · step 3 pending)        │
├──────────────────┬───────────────────────────────────────────────┤
│  左侧栏 (280px)   │  地图主区 (flex: 1, position: relative)        │
│                  │                                               │
│  ┌─ Config ────┐ │  [CartoDB Light 底图 · 复旦校区]               │
│  │ Steps        │ │                                               │
│  │ Time/Step    │ │  每个 Agent: L.circleMarker (r=10)            │
│  │ Start Time   │ │    颜色: wellness-based (红/橙/色板)           │
│  │ Concurrency  │ │    hover → tooltip (名字 + 当前意图)           │
│  │ [▶ Start]   │ │    click → 右侧详情抽屉                        │
│  └─────────────┘ │                                               │
│                  │  左上角覆盖层：Step X/N · 时间                  │
│  ┌─ History ───┐ │                                               │
│  │ ● sim-003   │ │  底部回放栏：◀ ▶ ────●──── X/N  [Auto ✓]       │
│  │   Completed │ │                                               │
│  │ ● sim-002   │ │  右侧详情抽屉（click Agent 后滑入）              │
│  │   Running   │ │                                               │
│  │ ● sim-001   │ │                                               │
│  │   Error     │ │                                               │
│  └─────────────┘ │                                               │
│                  │                                               │
│  [Next Step →]   │  ← viewingSimId 对应仿真 completed 才激活       │
│  (sticky bottom) │                                               │
└──────────────────┴───────────────────────────────────────────────┘
```

---

## 3. 左侧栏三区块

### 区块 A — Config

| 参数 | 控件 | 默认值 |
|------|------|--------|
| Simulation Steps | range slider 1–24 | 12 |
| Time per Step | select (30min/1h/2h/3h) | 1h |
| Start Time | datetime-local | 2024-09-02T08:00 |
| LLM Concurrency | range slider 1–20 | 5 |

底部：**Start Simulation ▶** 主按钮

按钮状态：
- 空闲 / 历史查看中 → 紫色激活，可点击（允许随时启动新仿真）
- 当前有仿真运行中 → 灰色禁用，显示 `● Running X/N`

点击逻辑：
```javascript
async function startSim() {
  const agentParams = JSON.parse(localStorage.getItem('agentParams') || '{}')
  const params = {
    num_agents:   agentParams.num_agents ?? 10,
    num_steps:    cfgSteps.value,
    tick_seconds: cfgTick.value,
    concurrency:  cfgConcurrency.value,
    start_time:   cfgStartTime.value.replace('T', ' ') + ':00',
  }
  const { sim_id } = await createSimulation(params)
  activeSimId.value   = sim_id
  viewingSimId.value  = sim_id    // 新仿真自动切换地图视图
  simRunning.value    = true
  connectSSE(sim_id)
  await loadHistory()
}
```

### 区块 B — History

- 进入页面时调用 `GET /api/simulations`，填充列表
- 按 start_time 倒序排列（最新在上）
- 每行显示：时间 · 参数摘要 · 状态 badge
- 点击某条 → `loadSimulation(sim_id)` 加载到地图
- 当前 `viewingSimId` 高亮
- 运行中的仿真每 3s 轮询更新状态

历史条目展示格式：
```
● 09/02 10:30 · 10人 · 12步 · 1h    ← 点击加载
  ✓ Completed
```

```
● 09/02 09:15 · 8人 · 8步 · 30min
  ↻ Running (5/8)
```

### 区块 C — Next Step（sticky bottom）

```javascript
// 激活条件：当前地图展示的仿真已完成
const canProceed = computed(() => {
  const sim = historyList.value.find(s => s.sim_id === viewingSimId.value)
  return sim?.status === 'completed'
})

function handleNextStep() {
  localStorage.setItem('simResult', JSON.stringify({
    sim_id:      viewingSimId.value,
    total_steps: viewingSteps.value.length,
    agents:      viewingSteps.value.at(-1)?.agents ?? [],
  }))
  router.push('/online-sim')
}
```

按钮状态：
- `canProceed = true` → 紫色渐变，`Next Step →`
- `canProceed = false` → 灰色禁用，`Next Step →`（tooltip 提示原因）

---

## 4. 前端状态模型

```javascript
// ── 仿真参数（Config 区块）──
const cfgSteps       = ref(12)
const cfgTick        = ref(3600)
const cfgStartTime   = ref('2024-09-02T08:00')
const cfgConcurrency = ref(5)

// ── 当前正在运行的仿真（SSE）──
const activeSimId  = ref(null)     // POST 后获得，SSE 连接的目标
const simRunning   = ref(false)    // 是否有 SSE 在跑

// ── 当前地图展示的仿真（可能是历史记录）──
const viewingSimId    = ref(null)
const viewingSteps    = ref([])    // 该仿真的全部步骤数据
const viewingStatus   = ref('idle') // 该仿真的状态
const viewingTotal    = ref(0)     // 该仿真的计划总步数
const displayIdx      = ref(-1)    // 地图回放游标
const autoFollow      = ref(true)  // 是否自动追尾最新步骤

// ── 历史列表 ──
const historyList = ref([])        // GET /api/simulations 的结果

// ── 工作流导航 ──
const canProceed = computed(() =>
  historyList.value.find(s => s.sim_id === viewingSimId.value)?.status === 'completed'
)

// ── 当前展示步骤 ──
const currentStepData = computed(() => viewingSteps.value[displayIdx.value] ?? null)
const agentList       = computed(() => currentStepData.value?.agents ?? [])

// ── Agent 元数据（来自 getSimulation）──
const agentsMeta = ref({})   // { [id]: { name, occupation, gender, ... } }

// ── 右侧抽屉 ──
const selectedId  = ref(null)
const detailAgent = computed(() =>
  currentStepData.value?.agents.find(a => a.id === selectedId.value) ?? null
)
const agentHistory = computed(() => {
  if (!selectedId.value) return []
  return viewingSteps.value
    .slice(0, (displayIdx.value < 0 ? 0 : displayIdx.value) + 1)
    .map(s => ({
      step:     s.step,
      sim_time: s.sim_time,
      ...s.agents.find(a => a.id === selectedId.value),
    }))
    .filter(r => r.intention !== undefined)
    .reverse()
})
```

---

## 5. SSE 接收逻辑

```javascript
let sseConn = null

function connectSSE(simId) {
  if (sseConn) { sseConn.close(); sseConn = null }
  sseConn = new EventSource(sseUrl(simId))

  sseConn.onmessage = e => {
    const ev = JSON.parse(e.data)
    if (ev.type === 'heartbeat') return

    if (ev.type === 'step') {
      // 追加到 activeSimId 对应的步骤缓存
      if (!viewingSteps.value.find(s => s.step === ev.step) &&
          viewingSimId.value === simId) {
        viewingSteps.value.push(ev)
        viewingSteps.value.sort((a, b) => a.step - b.step)
      }
      // 如果正在 viewing 这个仿真，且 autoFollow，则更新地图
      if (viewingSimId.value === simId && autoFollow.value) {
        displayIdx.value = viewingSteps.value.length - 1
        updateMarkers(ev)
      }
    }

    if (ev.type === 'complete') {
      simRunning.value = false
      sseConn.close(); sseConn = null
      loadHistory()   // 刷新历史列表，更新状态 badge
    }

    if (ev.type === 'error') {
      simRunning.value = false
      sseConn.close(); sseConn = null
      loadHistory()
    }
  }

  sseConn.onerror = () => {
    if (sseConn) { sseConn.close(); sseConn = null }
    if (simRunning.value) setTimeout(() => connectSSE(simId), 3000)
  }
}
```

---

## 6. 加载历史仿真到地图

```javascript
async function loadSimulation(simId) {
  viewingSimId.value = simId
  selectedId.value   = null
  displayIdx.value   = -1
  viewingSteps.value = []

  // 获取元数据
  const meta = await getSimulation(simId)
  agentsMeta.value = {}
  ;(meta.agents || []).forEach(a => { agentsMeta.value[a.id] = a })
  viewingTotal.value  = meta.total_steps || 0
  viewingStatus.value = meta.status

  // 获取所有已完成步骤
  const steps = await getSimulationSteps(simId)
  viewingSteps.value = steps.sort((a, b) => a.step - b.step)

  // 显示最新步骤
  if (viewingSteps.value.length) {
    displayIdx.value = viewingSteps.value.length - 1
    updateMarkers(viewingSteps.value[displayIdx.value])
  }

  // 如果仍在运行，且不是当前 SSE 目标，重新连
  if (meta.status === 'running' && simId !== activeSimId.value) {
    activeSimId.value = simId
    simRunning.value  = true
    connectSSE(simId)
  }
}
```

---

## 7. onMounted 流程

```javascript
onMounted(async () => {
  initMap()
  await loadHistory()
  // 默认加载最新一条仿真（如有）
  if (historyList.value.length) {
    await loadSimulation(historyList.value[0].sim_id)
  }
})
```

不再 auto-start，用户主动点击 Start Simulation 才触发。

---

## 8. 地图

```javascript
// 底图：CartoDB Light（与浅色主题一致）
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
  attribution: '© OSM © CARTO', subdomains: 'abcd', maxZoom: 19
}).addTo(mapInstance)

// Agent marker（L.circleMarker，统一圆形）
const AGENT_COLORS = ['#FF6B35','#004E89','#7B2D8E','#1A936F','#C5283D',
                      '#E9724C','#3498db','#9b59b6','#27ae60','#f39c12']

function agentFillColor(agent) {
  const w = wellness(agent.needs)
  if (w < 0.30)  return '#ef4444'   // 紧迫 → 红
  if (w < 0.55)  return '#f97316'   // 偏低 → 橙
  return AGENT_COLORS[(agent.id ?? 0) % AGENT_COLORS.length]
}

// 创建 / 更新 marker
function updateMarkers(stepData) {
  stepData.agents.forEach(agent => {
    const { lat, lng } = agent.position ?? {}
    if (!lat || !lng) return
    const color = agentFillColor(agent)
    if (markers[agent.id]) {
      markers[agent.id].setLatLng([lat, lng]).setStyle({ fillColor: color })
      markers[agent.id].setTooltipContent(`<b>${agent.name}</b><br>${agent.intention ?? ''}`)
    } else {
      markers[agent.id] = L.circleMarker([lat, lng], {
        radius: 10, fillColor: color, color: '#fff', weight: 2.5, fillOpacity: 0.95
      })
      .bindTooltip(`<b>${agent.name}</b><br>${agent.intention ?? ''}`,
                   { sticky: true, className: 'agent-tooltip' })
      .on('click', () => openDetail(agent.id))
      .addTo(mapInstance)
    }
  })
}
```

---

## 9. Agent 详情抽屉

点击 marker / 左侧 Agent 列表 → 右侧抽屉滑入

内容（从上到下）：
1. **Header**：头像（wellness 色）+ 姓名 + 职业/性别
2. **Current Needs**：4 条进度条（Satiety / Energy / Safety / Social）
3. **Current Intention**：意图 + 推理 + 执行结果
4. **Event History**：全部已显示步骤的时间轴，最新在上

---

## 10. 底部回放栏

```
[◀] [▶]   ────────●────────   Step 3 / 12   [Auto ✓]
```

- ◀ / ▶：`displayIdx ± 1`（在 `viewingSteps` 范围内）
- Slider：直接跳到任意已缓存步骤
- Auto：勾选后，新步骤到达时自动前进 displayIdx（默认开）
- **与 Next Step 工作流按钮完全无关**

---

## 11. 样式规范

与 SetupView 完全一致（不单独覆盖 CSS 变量）：
- `var(--bg)` / `var(--surface)` / `var(--border)` / `var(--purple)` / `var(--grad)` 等
- 区块标题：`cfg-section-title`（10px uppercase + 紫色 + border-bottom）
- 主按钮：`background: var(--grad)` 紫色渐变
- 卡片：`background: var(--surface); border: 1px solid var(--border); border-radius: 10px`

---

## 12. 风险与注意点

| 风险 | 处理方式 |
|------|---------|
| SSE 断线 | `onerror` 3s 后重连；重连前 `GET /steps` 补全缺失步骤 |
| Agent 位置为 null | 用上一步坐标兜底；首步为 null 则显示复旦中心默认坐标 |
| `agentParams` 不存在 | 默认 `num_agents=10` |
| 用户切换 viewing 仿真时仍有 SSE 在跑 | SSE 仍运行（`activeSimId`），只是地图不跟随；用户点 history 条目可随时切回 |
| 页面离开清理 | `onBeforeUnmount` 关闭 SSE + `mapInstance.remove()` |

---

## 13. 改动文件

- `frontend/src/views/SimulationView.vue` — 完全重写
- 不涉及 router、api、其他组件
