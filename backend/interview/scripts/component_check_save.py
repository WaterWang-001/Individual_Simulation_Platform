from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

import server


def _save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_checks() -> List[Tuple[str, Dict[str, Any]]]:
    survey = {
        "survey_name": "儿童流感疫苗认知访谈",
        "questions": [
            {"id": 1, "question": "请先介绍一下孩子的年龄和健康情况。", "type": "text_input"},
            {"id": 2, "question": "你通常通过哪些渠道了解儿童流感相关信息？", "type": "text_input"},
            {"id": 3, "question": "你怎么看待儿童接种流感疫苗这件事？", "type": "text_input"},
            {"id": 4, "question": "如果最终没有接种，最主要的顾虑是什么？", "type": "text_input"},
        ],
    }

    outputs: List[Tuple[str, Dict[str, Any]]] = []

    task = server.create_interview_task(
        topic="儿童流感疫苗认知",
        target_population="有学龄前儿童的家长",
        research_goal="了解家长对流感风险、信息来源、接种顾虑与决策逻辑的看法",
        survey=survey,
        sample_size=3,
        report_style="professional",
        constraints={"event_policy": {"enabled": False, "trigger_prob": 0.0}},
        user_need="我需要为一次家长访谈项目生成可执行的访谈任务和最终报告。",
    )
    outputs.append(("01_create_interview_task", task))

    personas = server.generate_candidate_personas(
        task=task["task"],
        diversity_requirements=["至少包含支持、犹豫、保留三类态度", "覆盖不同信息渠道依赖差异"],
    )
    outputs.append(("02_generate_candidate_personas", personas))

    review = server.review_persona_pool(task=task["task"], personas=personas["personas"])
    outputs.append(("03_review_persona_pool", review))

    plan = server.generate_interview_plan(task=task["task"])
    outputs.append(("04_generate_interview_plan", plan))

    outline = server.generate_interview_outline(
        topic="儿童流感疫苗认知",
        research_goal="获取家长对风险、接种和障碍的关键看法",
        target_population="有学龄前儿童的家长",
        user_need="生成可直接进入自动化访谈的提纲",
    )
    outputs.append(("05_generate_interview_outline", outline))

    persona = personas["personas"][0]
    stage = server.plan_interview_stage(task=task["task"], plan=plan["plan"], history=[], filled_slots={}, answered_ids=[], used_turns=0)
    outputs.append(("06_plan_interview_stage", stage))

    draft = server.draft_next_question(
        task=task["task"],
        plan=plan["plan"],
        persona=persona,
        history=[],
        filled_slots={},
        answered_ids=[],
        skipped_ids=[],
        used_turns=0,
    )
    outputs.append(("07_draft_next_question", draft))

    simulated = server.simulate_interviewee_reply(
        task=task["task"],
        persona=persona,
        question=draft["target_question"],
        history=[],
        stage_context=stage["stage"],
        event_policy={"enabled": False, "trigger_prob": 0.0},
    )
    outputs.append(("08_simulate_interviewee_reply", simulated))

    manual_history = [
        {"role": "interviewer", "content": draft["question_text"]},
        {"role": "interviewee", "content": simulated["simulation"]["reply"]},
    ]

    filled = server.fill_questionnaire_from_history(
        task=task["task"],
        plan=plan["plan"],
        history=manual_history,
        filled_slots={str(draft["target_question"]["id"]): simulated["simulation"]["reply"]},
    )
    outputs.append(("09_fill_questionnaire_from_history", filled))

    persona_from_answers = server.build_persona_from_answers(
        answers={str(q["id"]): q.get("answer") for q in filled["filled_questionnaire"].get("questions", []) if q.get("answer") not in [None, ""]}
    )
    outputs.append(("10_build_persona_from_answers", persona_from_answers))

    individual = server.summarize_individual_interview(
        task=task["task"],
        persona=persona,
        history=manual_history,
        filled_questionnaire=filled["filled_questionnaire"],
        user_need="我需要知道这个家长的核心顾虑、决策逻辑与后续沟通建议。",
    )
    outputs.append(("11_summarize_individual_interview", individual))

    insights = server.extract_research_insights_from_interview(
        task=task["task"],
        persona=persona,
        history=manual_history,
        filled_questionnaire=filled["filled_questionnaire"],
    )
    outputs.append(("12_extract_research_insights_from_interview", insights))

    single_run = server.run_single_interview(
        task=task["task"],
        persona=persona,
        plan=plan["plan"],
        event_policy={"enabled": False, "trigger_prob": 0.0},
    )
    outputs.append(("13_run_single_interview", single_run))

    aggregate = server.aggregate_interview_results(
        task=task["task"],
        interview_results=[single_run["result"]],
    )
    outputs.append(("14_aggregate_interview_results", aggregate))

    report = server.generate_professional_report(
        task=task["task"],
        personas=personas["personas"],
        interview_results=[single_run["result"]],
        aggregation=aggregate["aggregation"],
    )
    outputs.append(("15_generate_professional_report", report))

    score = server.score_questionnaire(
        questionnaire={
            "questions": [
                {"id": 1, "type": "single_choice", "options": ["A", "B"]},
                {"id": 2, "type": "Likert", "scale": ["非常不同意", "不同意", "一般", "同意", "非常同意"]},
                {"id": 3, "type": "text_input"},
            ]
        },
        filled_questionnaire={
            "questions": [
                {"id": 1, "answer": "a"},
                {"id": 2, "answer": "同意"},
                {"id": 3, "answer": "Influenza vaccine awareness"},
            ]
        },
        ground_truth={"1": "A", "2": "非常同意", "3": "influenza vaccine awareness"},
    )
    outputs.append(("16_score_questionnaire", score))

    legacy_cases = server.legacy_list_benchmark_cases(clean_only=True)
    outputs.append(("17_legacy_list_benchmark_cases", legacy_cases))

    return outputs


if __name__ == "__main__":
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = PLUGIN_ROOT / "outputs" / "component_checks" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    checks = _build_checks()
    index = []
    for name, payload in checks:
        path = out_dir / f"{name}.json"
        _save_json(path, payload)
        index.append({"name": name, "file": path.name, "ok": payload.get("ok") if isinstance(payload, dict) else None})

    summary = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "output_dir": str(out_dir),
        "check_count": len(index),
        "checks": index,
    }
    _save_json(out_dir / "00_index.json", summary)

    print(json.dumps({
        "ok": True,
        "output_dir": str(out_dir),
        "files": [item["file"] for item in index] + ["00_index.json"],
    }, ensure_ascii=False, indent=2))
