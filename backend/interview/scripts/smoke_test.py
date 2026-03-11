from __future__ import annotations

import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

import server


if __name__ == "__main__":
    survey = {
        "survey_name": "儿童流感认知访谈",
        "questions": [
            {"id": 1, "question": "请先介绍一下孩子的年龄和健康情况。", "type": "text_input"},
            {"id": 2, "question": "你怎么看待流感疫苗？", "type": "text_input"},
        ],
    }
    task_demo = server.create_interview_task(
        topic="儿童流感疫苗认知",
        target_population="有学龄前儿童的家长",
        research_goal="了解家长对流感风险和流感疫苗的认知、顾虑与决策逻辑",
        survey=survey,
        sample_size=3,
    )
    outline_demo = server.generate_interview_outline(
        topic="儿童流感疫苗认知",
        research_goal="获取家长对风险、接种和障碍的关键看法",
        target_population="有学龄前儿童的家长",
    )
    score_demo = server.score_questionnaire(
        questionnaire={
            "questions": [
                {"id": 1, "type": "single_choice", "options": ["A", "B"]},
                {"id": 2, "type": "Likert", "scale": ["非常不同意", "不同意", "一般", "同意", "非常同意"]},
            ]
        },
        filled_questionnaire={"questions": [{"id": 1, "answer": "a"}, {"id": 2, "answer": "同意"}]},
        ground_truth={"1": "A", "2": "非常同意"},
    )
    payload = {
        "project_map": server.get_project_map(),
        "task_demo": task_demo,
        "outline_demo": outline_demo,
        "score_demo": score_demo,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:8000])
