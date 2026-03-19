# HomeView 方案

> **职责**：项目主页 / Landing Page，介绍平台功能，引导用户进入仿真流程

---

## 1. 页面定位

```
/  (HomeView)  ──[Start Simulation]──▶  /setup  (SetupView)
```

不属于三阶段工作流，是独立的展示页面。

---

## 2. 当前实现状态

`HomeView.vue` 已完成，功能完整，无需改动。

### 已有内容

| 区块 | 内容 |
|------|------|
| NavBar | 固定顶部，居中导航链接，Logo |
| Hero | 大标题 "Simulate Human Behavior"，副标题，CTA 按钮 |
| Feature Cards | 三张卡片：Persona Simulation / Scenario-based Planning / Long-term Evolution |
| Demo Section | 四步流程（Configure → Relationships → Simulate → Analyze） |
| Footer | 版权信息 |

### 技术细节

- 背景：紫色点阵网格 + 渐变光晕动画（CSS keyframes）
- Scroll reveal：IntersectionObserver，元素进入视口时 fadeUp
- 全部为静态内容，无 API 调用
- 响应式：`@media (max-width: 768px)` 已适配

---

## 3. 当前状态

✅ **无需改动**

---

## 4. 潜在后续优化（非必须）

- Hero 区增加实际仿真截图 / 演示 GIF
- Feature Cards 内容可根据最终产品功能更新文案
- "Try Example Scenario" 按钮目前与 "Start Simulation" 指向同一路由（`/setup`），后续可指向预填充的示例参数
