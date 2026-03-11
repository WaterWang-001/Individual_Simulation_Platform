# auto-interview-orchestrator

目标：围绕自动化访谈产品主链路组织工具调用，而不是 benchmark 对比。

## 推荐调用顺序

1. `create_interview_task`
2. `generate_candidate_personas`
3. `generate_interview_plan`
4. `run_single_interview`
5. `aggregate_interview_results`
6. `generate_professional_report`

## 辅助工具

- `review_persona_pool`
- `plan_interview_stage`
- `draft_next_question`
- `simulate_interviewee_reply`
- `fill_questionnaire_from_history`
- `summarize_individual_interview`
- `extract_research_insights_from_interview`
- `build_persona_from_answers`
- `score_questionnaire`

## 原则

- 默认使用低干扰访谈，只有显式要求时才开启事件策略
- 报告结论必须回应研究目标
- persona 样本要有差异覆盖，避免同质化
- 单对象结论与群体报告分开生成
