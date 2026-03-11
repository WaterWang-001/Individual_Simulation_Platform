# Tool Examples

## 1. create_interview_task

输入：
```json
{
  "topic": "儿童流感疫苗认知",
  "target_population": "有学龄前儿童的家长",
  "research_goal": "了解家长对流感风险、流感疫苗和接种障碍的看法",
  "sample_size": 4,
  "report_style": "professional",
  "survey": {
    "survey_name": "儿童流感访谈",
    "questions": [
      {"id": 1, "question": "请先介绍一下孩子的年龄和健康情况。", "type": "text_input"},
      {"id": 2, "question": "你怎么看待流感疫苗？", "type": "text_input"}
    ]
  }
}
```

输出核心字段：
```json
{
  "ok": true,
  "task": {
    "task_id": "...",
    "topic": "儿童流感疫苗认知",
    "target_population": "有学龄前儿童的家长",
    "research_goal": "了解家长对流感风险、流感疫苗和接种障碍的看法",
    "sample_size": 4,
    "report_style": "professional"
  }
}
```

## 2. generate_candidate_personas + generate_interview_plan

输入：
```json
{
  "task": {"topic": "儿童流感疫苗认知", "target_population": "有学龄前儿童的家长", "sample_size": 4}
}
```

输出关注：
- `personas[*].diversity_tags`
- `plan.stages`
- `plan.must_cover_ids`

## 3. run_single_interview

输入：
```json
{
  "task": {"topic": "儿童流感疫苗认知", "research_goal": "..."},
  "persona": {"persona_id": "persona_01", "profile_summary": "..."},
  "plan": {"stages": [...], "questions": [...], "must_cover_ids": [1, 2]},
  "event_policy": {"enabled": false, "trigger_prob": 0.0}
}
```

输出关注：
- `result.history`
- `result.filled_questionnaire`
- `result.subject_report`
- `result.research_insights`

## 4. aggregate_interview_results + generate_professional_report

输入：
```json
{
  "task": {"topic": "儿童流感疫苗认知", "research_goal": "..."},
  "interview_results": [{"persona_id": "persona_01"}, {"persona_id": "persona_02"}]
}
```

输出关注：
- `aggregation.common_patterns`
- `aggregation.differences`
- `report.executive_summary`
- `report.recommendations`

## 5. score_questionnaire

输入：
```json
{
  "questionnaire": {
    "questions": [
      {"id": 1, "type": "single_choice", "options": ["A", "B"]},
      {"id": 2, "type": "Likert", "scale": ["非常不同意", "不同意", "一般", "同意", "非常同意"]}
    ]
  },
  "filled_questionnaire": {
    "questions": [
      {"id": 1, "answer": "a"},
      {"id": 2, "answer": "同意"}
    ]
  },
  "ground_truth": {"1": "A", "2": "非常同意"}
}
```

输出关注：
- `score.score`
- `score.by_type`
