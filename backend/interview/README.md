# FastMCP Auto-Interview Orchestration Server

这个目录现在定位为一个“自动化访谈 orchestration server”，核心目标不是 benchmark 对比，而是把主题定义、persona 生成、访谈规划、单场访谈执行、单体总结和多对象报告串成一条可调用链路。

## 主流程能力

- `create_interview_task`
- `generate_candidate_personas`
- `generate_interview_plan`
- `run_single_interview`
- `aggregate_interview_results`
- `generate_professional_report`

## 原子能力工具

- `generate_interview_outline`
- `review_persona_pool`
- `plan_interview_stage`
- `draft_next_question`
- `simulate_interviewee_reply`
- `fill_questionnaire_from_history`
- `summarize_individual_interview`
- `extract_research_insights_from_interview`
- `score_questionnaire`
- `build_persona_from_answers`

## Legacy / Admin 工具

这些保留为兼容与调试用途，不是主产品链路：

- `legacy_list_benchmark_cases`
- `legacy_read_benchmark_case`
- `legacy_analyze_outputs`
- `legacy_compare_models_by_survey`
- `legacy_find_representative_cases`
- `legacy_read_output_record`

## 默认行为

- 默认低干扰访谈：除非显式传入 `event_policy.enabled=true`，否则不触发异常事件
- `score_questionnaire` 按题型分别计分
- 单选题和文本对比忽略大小写
- Likert 量表按与真实答案的距离递减给分

## 快速启动

```bash
cd fastmcp_claude_plugin
pip install -r requirements.txt
cp project_config.sample.json project_config.local.json
# 或者继续使用 project_config.json；推荐本地文件 + 环境变量，不要提交真实 key
export DASHSCOPE_API_KEY=YOUR_DASHSCOPE_KEY
export DEEPSEEK_API_KEY=YOUR_DEEPSEEK_KEY
export OPENAI_API_KEY=YOUR_OPENAI_KEY
python3 scripts/smoke_test.py
python3 scripts/run_server.py
```

说明：

- `scripts/run_server.py` 会先做启动前自检，明确提示是 `fastmcp` 缺失、模型配置缺失，还是将以规则回退模式运行。
- 没有模型配置或网络不可达时，大部分主流程工具会返回 fallback 结果，并在响应里携带 warning。
- `project_config.json` / `project_config.local.json` 不应保存明文 API key，推荐改用 `api_key_env` + 环境变量。

## 目录说明

- `server.py`：FastMCP 工具注册入口
- `toolkit.py`：工具实现与主链路编排
- `config.py` / `paths.py`：配置与路径解析
- `project_config.sample.json`：模型配置模板
- `prompts/`：访谈任务、persona、计划、报告相关提示词
- `core/`：复用的 agent、evaluation、io、schema 层
- `scripts/smoke_test.py`：最小本地验证
- `scripts/component_check.py`：17 项组件级回归检查
- `scripts/run_server.py`：启动 FastMCP server
- `docs/tool-contracts.md`：工具契约
- `docs/tool-examples.md`：工具级示例
- `USAGE.md`：接入与使用手册
