# 使用手册

## 1. 安装

```bash
cd fastmcp_claude_plugin
pip install -r requirements.txt
cp project_config.sample.json project_config.local.json
export DASHSCOPE_API_KEY=YOUR_DASHSCOPE_KEY
export DEEPSEEK_API_KEY=YOUR_DEEPSEEK_KEY
export OPENAI_API_KEY=YOUR_OPENAI_KEY
```

如果不提供模型配置，工具仍可使用规则回退，但生成质量会下降。推荐把本地模型配置放在 `project_config.local.json`，并通过 `api_key_env` 从环境变量读取密钥，不要提交明文 key。

## 2. 本地验证

```bash
python3 scripts/smoke_test.py
python3 scripts/component_check.py
```

当前 smoke test 验证：

- `get_project_map`
- `create_interview_task`
- `generate_interview_outline`
- `score_questionnaire`

`component_check.py` 会串行验证 17 个工具，适合做回归检查；网络不可达时，应看到 fallback warning，但脚本不应崩溃。

## 3. 启动 MCP server

```bash
python3 scripts/run_server.py
```

默认使用 `stdio`。

启动脚本会先做自检：

- `fastmcp` 缺失时直接报错并退出
- 模型配置缺失或仍是模板值时给出 warning，并继续以规则回退模式启动
- 默认模型配置存在时只校验本地配置，不在启动前主动探测网络

## 4. Claude Desktop 接入

- 打开 `claude_desktop_config.sample.json`
- 把 `args[0]` 改成你本机 `scripts/run_server.py` 的绝对路径
- 合并到 Claude Desktop 的 MCP 配置文件
- 重启 Claude Desktop

## 5. 推荐调用顺序

### 闭环 1：创建任务

- `create_interview_task`

输入：
- `topic`
- `target_population`
- `research_goal`
- `survey`
- `sample_size`
- `report_style`
- `constraints`

输出：
- 标准化任务对象 `task`

### 闭环 2：生成 persona 与访谈计划

- `generate_candidate_personas`
- `generate_interview_plan`
- 可选：`review_persona_pool`
- 可选：`plan_interview_stage`

### 闭环 3：执行单场访谈

- `run_single_interview`

如果要手动单步推进，也可以改用：
- `draft_next_question`
- `simulate_interviewee_reply`
- `fill_questionnaire_from_history`

### 闭环 4：生成总结与总报告

- `summarize_individual_interview`
- `extract_research_insights_from_interview`
- `aggregate_interview_results`
- `generate_professional_report`

## 6. 事件策略

默认：

```json
{"enabled": false, "trigger_prob": 0.0}
```

只有显式开启时才触发异常事件，例如：

```json
{"enabled": true, "trigger_prob": 0.2, "event_type": "passive_noncooperation"}
```

## 7. 辅助工具

- `score_questionnaire`：按题型规则评分
- `build_persona_from_answers`：从结构化答案生成画像

## 8. Legacy 工具

若需要保留旧 benchmark 兼容能力，可调用：

- `legacy_list_benchmark_cases`
- `legacy_read_benchmark_case`
- `legacy_analyze_outputs`
- `legacy_compare_models_by_survey`
- `legacy_find_representative_cases`
- `legacy_read_output_record`

这些工具不属于主流程。
