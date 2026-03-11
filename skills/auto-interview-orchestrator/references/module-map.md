# 自动化问答模块地图

## 1. 数据源准备

- `prepare_benchmark_sources.py`
  - 把外部数据集整理为 `benchmark_sources/*`

## 2. Benchmark 构建

- `build_benchmark.py`
  - 从标准化数据源抽样
  - 生成问卷、真实答案、画像、事件计划

典型输出：

- `questionnaire.json`
- `ground_truth.json`
- `persona.json`
- `scenario_plan.json`
- `meta.json`

## 3. 访谈执行

- `run_benchmark.py`

核心职责：

- 生成问卷简介
- 规划阶段目标
- 决定下一动作
- 生成访谈问题
- 模拟受访者回答
- 注入异常事件
- 结构化回填
- 规则评分
- 生成最终画像与过程指标

## 4. 批量运行

- `run_all_benchmarks.py`

## 5. 结果分析

- `summarize_outputs.py`
- `outputs/*.jsonl`

## 6. Demo 展示

- `demo_web_streamlit/app.py`
- `demo_web_streamlit/backend_service.py`
- `demo_web_streamlit/preset_module.py`
- `demo_web_streamlit/live_module.py`

这里主要负责展示与交互，不是 benchmark 主逻辑来源。
