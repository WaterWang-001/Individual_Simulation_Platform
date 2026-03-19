# OnlineSimView 方案（v3）

> **职责**：Step 3 — 线上社交环境仿真（OASIS 框架）
> 将个体离线行为轨迹融入画像，模拟 Agent 在社交平台上的发帖/互动行为，并支持营销干预实验

---

## 1. 页面定位

```
Step 1: SetupView    Step 2: SimulationView    Step 3: OnlineSimView
  Agent 配置           个体行为仿真（地图）          线上社交平台仿真
                       Next Step ────────────▶  （当前页）
```

---

## 2. 数据流

### 2.1 输入（来自 Step 2）

```javascript
// localStorage('simResult')
{
  sim_id:      "sim_xxx",
  total_steps: 12,
  agents: [                         // 最终步骤每个 Agent 状态
    {
      id:          "user_001",
      name:        "张明",
      occupation:  "本科生",
      gender:      "male",
      needs:       { satiety, energy, safety, social },
      position:    { lat, lng },
      intention:   "去图书馆学习",
      event_history: [...]           // 全部步骤的事件记录
    }
  ]
}
```

### 2.2 画像融合逻辑（前端 → 后端 POST）

将 lifesim agent 映射为 OASIS CSV 格式：

| lifesim 字段 | OASIS 字段 | 映射规则 |
|---|---|---|
| `id` | `agent_id` / `user_id` | 直接使用 |
| `name` | `name` | 直接使用 |
| name → 小写去空格 | `username` | `zhangming` |
| occupation + interests | `bio` | `${occupation}，兴趣：${interests.join('、')}` |
| bio + event_history 摘要 | `description` | 拼接离线行为摘要（最多3条意图） |
| event_history + occupation | `user_char` | 生成角色扮演指令（含离线行为特征） |
| occupation → 分层规则 | `group` | 见下表 |
| relationships | `following_agentid_list` | 从 /api/relationships 筛选选中 agents 的关系 |
| 0.0 | `initial_attitude_[topic]` | 初始中立，由仿真动态演化 |

**群体分层规则：**

| occupation 关键词 | OASIS group |
|---|---|
| 博士 / 研究生 / 硕士 | 权威媒体/大V |
| 学生会 / 社团干部（由 occupation/interests 推断） | 活跃KOL |
| 活跃创作（多项 interests 含创作类） | 活跃创作者 |
| 本科生（默认） | 普通用户 |
| needs.social < 0.3 / 低活跃 | 潜水用户 |

---

## 3. 整体布局（v3 — 无 Tab 单页三区结构）

```
┌────────────────────────────────────────────────────────────────────────────┐
│  NavBar  (step 1 ✓ · step 2 ✓ · step 3 active)                             │
├──────────────────────┬─────────────────────────────────────────────────────┤
│  左侧栏 (320px)       │  右侧内容区 (flex:1, 分上下两块)                     │
│                      │                                                     │
│  [A] Agents          │  ┌─────────────────────────────────────────────┐   │
│      agent cards     │  │ 右上：Attitude 折线图（flex: 0 0 320px）      │   │
│      (群体badge)     │  │   · 各群体平均 attitude 随步骤折线           │   │
│                      │  │   · Y轴 -1~1，中线虚线，图例                 │   │
│  [B] Campaign        │  │   · 仿真完成后显示；运行中实时更新            │   │
│      Topic: ______   │  └─────────────────────────────────────────────┘   │
│      Steps: [4]      │  ┌─────────────────────────────────────────────┐   │
│      Concurrency:[3] │  │ 右下：Stats 数据面板（flex: 0 0 auto）        │   │
│                      │  │   · 5张摘要卡片（Posts/Likes/Reposts/        │   │
│  [C] Interventions   │  │     Comments/Actions）                       │   │
│      + Add row       │  │   · Group Activity 水平条形图                │   │
│      step|type|      │  │   · Top 5 最高互动帖子                       │   │
│      content|target  │  └─────────────────────────────────────────────┘   │
│                      │                                                     │
│  [▶ Start Sim]       │  左侧 Posts Feed（flex: 1, 可滚动）                  │
│  [● Running 2/4]     │  （与右侧上下区并列，各自独立滚动）                   │
└──────────────────────┴─────────────────────────────────────────────────────┘
```

### 精确网格结构

```
workspace
├── sidebar (320px, flex-shrink:0)          ← 左侧配置栏（同 v2）
└── main-area (flex:1, overflow:hidden)
    ├── posts-col (width:420px, flex-shrink:0, overflow-y:auto)   ← Posts Feed
    └── right-col (flex:1, overflow-y:auto)
        ├── attitude-panel (border-bottom)                         ← 折线图
        └── stats-panel                                            ← 数据汇总
```

---

## 4. 左侧栏三区块（不变）

### 区块 A — Agents

- 从 `simResult.agents` 渲染 Agent 卡片
- 每张卡片：头像圆圈（wellness色）+ 姓名 + 群体badge
- 群体badge颜色：
  - 权威媒体/大V → 蓝
  - 活跃KOL → 橙
  - 活跃创作者 → 绿
  - 普通用户 → 灰
  - 潜水用户 → 浅灰
- 卡片可展开查看 `user_char`（已融合离线行为的角色指令）

### 区块 B — Campaign

| 参数 | 控件 | 说明 |
|---|---|---|
| Campaign Topic | text input | 营销/研究主题，如 "TNT演唱会"，决定 attitude metric 名称 |
| Simulation Steps | range 1–12 | 默认 4 |
| Concurrency | range 1–10 | 默认 3 |

> LLM Model 由 `backend/marketing/data/.env` 中的 `MARS_MODEL_NAME` 决定，不暴露给用户。

### 区块 C — Interventions

可编辑表格，每行一条干预策略：

| 字段 | 说明 |
|---|---|
| Step | 触发步骤（1~N）|
| Type | broadcast / bribery / register_user |
| Content | 干预内容（广播文本 / 激励文本 / bot画像JSON）|
| Target Group | 目标群体（空=全体）|
| Ratio | 目标比例 0~1（仅bribery）|

---

## 5. 各区内容规格

### 5.1 Posts Feed（左侧主体）

- 标题栏：`Posts  [N条]` + 进度 `Step X / N`
- 帖子卡片（新帖插入顶部）：
  - 头像（群体色）+ 姓名 + 群体badge + Step标签
  - attitude chip（正/负/中立，带数值）
  - 正文内容
  - 若为转发/引用：显示 quote_content 引用块
  - 底部互动栏：👍 N · 👎 N · 🔁 N · 💬 N
- 背景微色：attitude > 0.3 → 浅绿；< -0.3 → 浅红；否则白

### 5.2 Attitude 折线图（右上）

- 标题：`Attitude towards "<topic>" by group`
- SVG 折线图，viewBox="0 0 560 220"
- X轴 = 步骤，Y轴 = -1~1，中线0用紫色虚线
- 每个群体一条线（5色），鼠标悬停显示数值
- 仿真进行中每步更新；完成后最终数据
- 图例行：各群体颜色点 + 名称

### 5.3 Stats 数据面板（右下）

**摘要卡片行（5格）**：
- Posts 总帖数
- Likes 总点赞
- Reposts 总转发
- Comments 总评论
- Actions 总行为数

**Group Activity 水平条形图**：
- 每行：群体色点 + 群体名 + 进度条（按最大帖数比例）+ `N posts · N 👍`

**Top 5 最高互动帖子**：
- 按 (num_likes + num_shares) 降序
- 每行：排名 # · 作者名 + 群体badge · 内容摘要 · 互动数

---

## 6. 后端 API（现状 ✅）

```
POST /api/online-sim/start         启动仿真，返回 online_sim_id
GET  /api/online-sim/<id>/stream   SSE 日志流 / step_done / complete
GET  /api/online-sim/<id>/posts    帖子列表（含 num_likes/shares/comments/step）
GET  /api/online-sim/<id>/attitude 态度轨迹（按群体聚合）
GET  /api/online-sim/<id>/stats    统计摘要（帖数/点赞/群体分布/Top5）
```

### 模型配置（后端只读）

- `MARS_MODEL_NAME`：从 `data/.env` 读取，默认 `deepseek-chat`
- `MARS_MODEL_BASE_URL` / `MARS_MODEL_API_KEY`：同上
- `OASIS_PYTHON_BIN`：指定 oasis conda 环境的 Python 路径

---

## 7. 前端状态模型

```javascript
// ── 输入数据 ──
const simResult    = ref(null)       // 从 localStorage 读取
const oasisAgents  = ref([])         // 前端映射的 OASIS 画像

// ── Campaign 配置 ──
const cfgTopic       = ref('')
const cfgSteps       = ref(4)
const cfgConcurrency = ref(3)

// ── 干预策略 ──
const interventions  = ref([])

// ── 仿真运行 ──
const onlineSimId   = ref(null)
const simRunning    = ref(false)
const simProgress   = ref(0)         // 当前步骤
const logs          = ref([])        // 运行日志

// ── 结果（三个区域各自的数据）──
const posts         = ref([])        // Posts Feed
const attitudeData  = ref(null)      // 折线图数据 {steps, groups}
const statsData     = ref(null)      // 统计面板数据
```

---

## 8. UX 细节

### 布局滚动行为
- 左侧配置栏：独立滚动
- Posts Feed 列：独立垂直滚动（overflow-y: auto）
- 右侧列：独立垂直滚动（attitude + stats 作为一个滚动容器）

### 实时更新节奏
- `step_done` 事件：刷新 posts（实时插入新帖）+ 刷新 attitude（折线更新）
- `complete` 事件：刷新 posts + attitude + stats（完整数据）

### 空状态
- Posts：未运行时显示 "Start the simulation to see agent posts in real time"
- Attitude / Stats：显示占位提示，无空白板

### 启动按钮（左侧底部）
- 空闲：`▶ Start Simulation`（紫色渐变）
- 运行中：`● Running 2/4`（灰色禁用 + pulse 动画）
- 完成：`✓ Completed`（绿色）

---

## 9. 样式规范

与 SetupView / SimulationView 保持一致：
- CSS 变量：`var(--bg)` / `var(--surface)` / `var(--border)` / `var(--purple)` / `var(--grad)`
- 左侧栏宽度 320px，同 SimulationView
- Posts Feed 列宽度 420px（固定），右侧列 flex:1
- 区块标题：`cfg-section-title` 样式

---

## 10. 改动文件

### 前端
- `frontend/src/views/OnlineSimView.vue` — 重构布局（无 Tab → 三区单页）✅ 待实现
- `frontend/src/api/index.js` — 已有 4 个 online-sim API 函数 ✅

### 后端
- `backend/marketing/__init__.py` ✅
- `backend/marketing/online_sim.py` ✅（含 /posts /attitude /stats）
- `backend/marketing/data/.env` — 已加 `MARS_MODEL_NAME=deepseek-chat` ✅
- `backend/marketing/simulation/oasis_test_grouping.py` — DEFAULT_MODEL_NAME 改为 deepseek-chat ✅
- `backend/app.py` ✅

---

## 11. 风险与处理

| 风险 | 处理方式 |
|---|---|
| 模型名不匹配 API | 从 .env 读取 MARS_MODEL_NAME，默认 deepseek-chat，不由前端传入 |
| subprocess 异步通信 | 写临时目录，用 online_sim_id 隔离多次运行 |
| OASIS DB 并发写入冲突 | 每次仿真用独立 DB 文件（`osim_{id}.db`）|
| 三区布局在小屏幕变形 | main-area min-width:900px，小屏水平滚动 |
| attitude 数据 agent_type='LLM' | 后端用 agent_map 将 agent_id 映射到群体名 |
