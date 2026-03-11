# Tool Contracts

## 主流程工具

### `create_interview_task`

输入：
- `topic: str`
- `target_population: str`
- `research_goal: str`
- `survey: dict | null`
- `sample_size: int`
- `report_style: str`
- `constraints: dict | null`
- `user_need: str`

输出：
- `task`
  - `task_id`
  - `topic`
  - `target_population`
  - `research_goal`
  - `sample_size`
  - `report_style`
  - `survey`
  - `constraints`
  - `warnings`

### `generate_candidate_personas`

输入：
- `task`
- `persona_pool: list | null`
- `diversity_requirements: list | null`

输出：
- `personas`
  - `persona_id`
  - `profile_summary`
  - `demographics`
  - `topic_attitudes`
  - `behavior_habits`
  - `decision_style`
  - `language_style`
  - `diversity_tags`
- `coverage_notes`

### `generate_interview_plan`

输入：
- `task`

输出：
- `plan`
  - `topic`
  - `intro_text`
  - `closing_prompt`
  - `stages`
  - `questions`
  - `must_cover_ids`
  - `sensitive_points`
  - `completion_rule`

### `run_single_interview`

输入：
- `task`
- `persona`
- `plan`
- `interviewer_model: str | null`
- `interviewee_model: str | null`
- `event_policy: dict | null`

输出：
- `result`
  - `persona_id`
  - `history`
  - `filled_questionnaire`
  - `final_profile`
  - `subject_report`
  - `research_insights`
  - `process_metrics`

### `aggregate_interview_results`

输入：
- `task`
- `interview_results`

输出：
- `aggregation`
  - `topic`
  - `sample_overview`
  - `common_patterns`
  - `differences`
  - `risks`
  - `recommendations`

### `generate_professional_report`

输入：
- `task`
- `personas`
- `interview_results`
- `aggregation: dict | null`

输出：
- `report`
  - `topic`
  - `executive_summary`
  - `methodology`
  - `sample_profile`
  - `key_findings`
  - `theme_analysis`
  - `population_segments`
  - `recommendations`
  - `limitations`

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

- `legacy_list_benchmark_cases`
- `legacy_read_benchmark_case`
- `legacy_analyze_outputs`
- `legacy_compare_models_by_survey`
- `legacy_find_representative_cases`
- `legacy_read_output_record`
