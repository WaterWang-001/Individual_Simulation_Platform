from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

import server


def _print_section(title: str, payload: Dict[str, Any]) -> None:
    print(f"\n===== {title} =====")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:12000])


def _require_ok(title: str, payload: Dict[str, Any], required_keys: Iterable[str] = ()) -> None:
    if not isinstance(payload, dict):
        raise AssertionError(f"{title} 返回值不是对象")
    if payload.get("ok") is not True:
        raise AssertionError(f"{title} 未返回 ok=true: {json.dumps(payload, ensure_ascii=False)}")
    for key in required_keys:
        if key not in payload:
            raise AssertionError(f"{title} 缺少关键字段: {key}")


if __name__ == "__main__":
    survey = {
        "survey_name": "儿童流感疫苗认知访谈",
        "questions": [
            {"id": 1, "question": "请先介绍一下孩子的年龄和健康情况。", "type": "text_input"},
            {"id": 2, "question": "你通常通过哪些渠道了解儿童流感相关信息？", "type": "text_input"},
            {"id": 3, "question": "你怎么看待儿童接种流感疫苗这件事？", "type": "text_input"},
            {"id": 4, "question": "如果最终没有接种，最主要的顾虑是什么？", "type": "text_input"},
        ],
    }

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
    _print_section("1. create_interview_task", task)
    _require_ok("create_interview_task", task, ["task"])

    personas = server.generate_candidate_personas(
        task=task["task"],
        diversity_requirements=["至少包含支持、犹豫、保留三类态度", "覆盖不同信息渠道依赖差异"],
    )
    _print_section("2. generate_candidate_personas", personas)
    _require_ok("generate_candidate_personas", personas, ["personas"])
    if not personas["personas"]:
        raise AssertionError("generate_candidate_personas 未生成 persona")

    review = server.review_persona_pool(task=task["task"], personas=personas["personas"])
    _print_section("3. review_persona_pool", review)
    _require_ok("review_persona_pool", review, ["review"])

    plan = server.generate_interview_plan(task=task["task"])
    _print_section("4. generate_interview_plan", plan)
    _require_ok("generate_interview_plan", plan, ["plan"])

    outline = server.generate_interview_outline(
        topic="儿童流感疫苗认知",
        research_goal="获取家长对风险、接种和障碍的关键看法",
        target_population="有学龄前儿童的家长",
        user_need="生成可直接进入自动化访谈的提纲",
    )
    _print_section("5. generate_interview_outline", outline)
    _require_ok("generate_interview_outline", outline, ["outline"])

    persona = personas["personas"][0]
    stage = server.plan_interview_stage(task=task["task"], plan=plan["plan"], history=[], filled_slots={}, answered_ids=[], used_turns=0)
    _print_section("6. plan_interview_stage", stage)
    _require_ok("plan_interview_stage", stage, ["stage"])

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
    _print_section("7. draft_next_question", draft)
    _require_ok("draft_next_question", draft, ["target_question", "question_text"])

    simulated = server.simulate_interviewee_reply(
        task=task["task"],
        persona=persona,
        question=draft["target_question"],
        history=[],
        stage_context=stage["stage"],
        event_policy={"enabled": False, "trigger_prob": 0.0},
    )
    _print_section("8. simulate_interviewee_reply", simulated)
    _require_ok("simulate_interviewee_reply", simulated, ["simulation"])

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
    _print_section("9. fill_questionnaire_from_history", filled)
    _require_ok("fill_questionnaire_from_history", filled, ["filled_questionnaire"])

    persona_from_answers = server.build_persona_from_answers(
        answers={str(q["id"]): q.get("answer") for q in filled["filled_questionnaire"].get("questions", []) if q.get("answer") not in [None, ""]}
    )
    _print_section("10. build_persona_from_answers", persona_from_answers)
    _require_ok("build_persona_from_answers", persona_from_answers, ["persona"])

    individual = server.summarize_individual_interview(
        task=task["task"],
        persona=persona,
        history=manual_history,
        filled_questionnaire=filled["filled_questionnaire"],
        user_need="我需要知道这个家长的核心顾虑、决策逻辑与后续沟通建议。",
    )
    _print_section("11. summarize_individual_interview", individual)
    _require_ok("summarize_individual_interview", individual, ["report"])

    insights = server.extract_research_insights_from_interview(
        task=task["task"],
        persona=persona,
        history=manual_history,
        filled_questionnaire=filled["filled_questionnaire"],
    )
    _print_section("12. extract_research_insights_from_interview", insights)
    _require_ok("extract_research_insights_from_interview", insights, ["insights"])

    single_run = server.run_single_interview(
        task=task["task"],
        persona=persona,
        plan=plan["plan"],
        event_policy={"enabled": False, "trigger_prob": 0.0},
    )
    _print_section("13. run_single_interview", single_run)
    _require_ok("run_single_interview", single_run, ["result"])
    if not single_run["result"].get("history"):
        raise AssertionError("run_single_interview 未返回 history")

    aggregate = server.aggregate_interview_results(
        task=task["task"],
        interview_results=[single_run["result"]],
    )
    _print_section("14. aggregate_interview_results", aggregate)
    _require_ok("aggregate_interview_results", aggregate, ["aggregation"])

    report = server.generate_professional_report(
        task=task["task"],
        personas=personas["personas"],
        interview_results=[single_run["result"]],
        aggregation=aggregate["aggregation"],
    )
    _print_section("15. generate_professional_report", report)
    _require_ok("generate_professional_report", report, ["report"])

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
    _print_section("16. score_questionnaire", score)
    _require_ok("score_questionnaire", score, ["score"])

    legacy_cases = server.legacy_list_benchmark_cases(clean_only=True)
    _print_section("17. legacy_list_benchmark_cases", legacy_cases)
    _require_ok("legacy_list_benchmark_cases", legacy_cases)

    print("\nAll 17 component checks passed.")
