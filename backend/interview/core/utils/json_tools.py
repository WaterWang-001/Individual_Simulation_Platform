from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List

from ..schemas.common import ModelConfig
from ..services.llm_service import call_llm_with_retry


def extract_json(text: str) -> Any:
    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object detected in model output.")
    json_str = match.group()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*]", "]", json_str)
        return json.loads(json_str)


def is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_action_json(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    allowed = {
        "ask_question",
        "follow_up",
        "clarify",
        "skip_question",
        "handle_refusal",
        "handle_off_topic",
        "empathy",
        "conclude",
        "plan",
    }
    return obj.get("action") in allowed and "target_question_id" in obj and "reason_tag" in obj


def validate_plan_json(obj: Any) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("missing"), list) and isinstance(obj.get("next_steps"), list) and "summary" in obj


def validate_structured_answers_json(obj: Any) -> bool:
    if not isinstance(obj, dict) or not isinstance(obj.get("answers"), list):
        return False
    for answer in obj["answers"]:
        if not isinstance(answer, dict) or "id" not in answer or "answer" not in answer:
            return False
    return True


def validate_questionnaire_summary_json(obj: Any) -> bool:
    return isinstance(obj, dict) and is_non_empty_str(obj.get("intro_text")) and isinstance(obj.get("summary"), dict)


def validate_final_profile_json(obj: Any) -> bool:
    required = {
        "profile_summary",
        "questionnaire_traits",
        "general_personality_traits",
        "communication_style",
        "consistency_and_conflicts",
        "risk_signals",
        "insights",
        "next_interview_suggestions",
    }
    return isinstance(obj, dict) and required.issubset(set(obj.keys()))


def validate_questionnaire_filled_json(obj: Any) -> bool:
    if not isinstance(obj, dict) or not isinstance(obj.get("questions"), list):
        return False
    for q in obj["questions"]:
        if not isinstance(q, dict) or "id" not in q:
            return False
    return True


def validate_interview_task_json(obj: Any) -> bool:
    required = {"task_id", "topic", "target_population", "research_goal", "sample_size", "report_style", "survey", "constraints", "warnings"}
    return isinstance(obj, dict) and required.issubset(set(obj.keys()))


def validate_candidate_personas_json(obj: Any) -> bool:
    if not isinstance(obj, dict) or not isinstance(obj.get("personas"), list):
        return False
    for persona in obj["personas"]:
        if not isinstance(persona, dict):
            return False
        required = {"persona_id", "profile_summary", "demographics", "topic_attitudes", "behavior_habits", "decision_style", "language_style", "diversity_tags"}
        if not required.issubset(set(persona.keys())):
            return False
    return isinstance(obj.get("coverage_notes", []), list)


def validate_persona_pool_review_json(obj: Any) -> bool:
    required = {"coverage_ok", "homogeneity_risk", "missing_segments", "recommendations"}
    return isinstance(obj, dict) and required.issubset(set(obj.keys()))


def validate_interview_plan_json(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    required = {"topic", "intro_text", "closing_prompt", "stages", "questions", "must_cover_ids", "sensitive_points", "completion_rule"}
    if not required.issubset(set(obj.keys())):
        return False
    if not isinstance(obj.get("stages"), list) or not isinstance(obj.get("questions"), list):
        return False
    for stage in obj["stages"]:
        if not isinstance(stage, dict):
            return False
        if not {"stage_id", "stage_name", "stage_goal", "question_ids"}.issubset(set(stage.keys())):
            return False
    for question in obj["questions"]:
        if not isinstance(question, dict):
            return False
        if not {"id", "question", "type", "stage_name", "intent", "optional", "followup_hint"}.issubset(set(question.keys())):
            return False
    return isinstance(obj.get("completion_rule"), dict)


def validate_stage_plan_json(obj: Any) -> bool:
    required = {"current_stage", "stage_goal", "must_cover_remaining", "next_focus", "used_turns"}
    return isinstance(obj, dict) and required.issubset(set(obj.keys()))


def validate_simulated_reply_json(obj: Any) -> bool:
    required = {"reply", "event", "state_hint"}
    return isinstance(obj, dict) and required.issubset(set(obj.keys()))


def validate_interview_outline_json(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    required = {"topic", "survey_name", "interview_goal", "intro_text", "stages", "questions", "closing_prompt"}
    if not required.issubset(set(obj.keys())):
        return False
    if not isinstance(obj.get("stages"), list) or not isinstance(obj.get("questions"), list):
        return False
    return True


def validate_subject_report_json(obj: Any) -> bool:
    required = {
        "topic",
        "user_need_response",
        "subject_summary",
        "questionnaire_aligned_findings",
        "traits_and_patterns",
        "risks_and_concerns",
        "actionable_recommendations",
        "evidence_trace",
        "confidence_notes",
    }
    return isinstance(obj, dict) and required.issubset(set(obj.keys()))


def validate_individual_summary_json(obj: Any) -> bool:
    return validate_subject_report_json(obj)


def validate_research_insights_json(obj: Any) -> bool:
    required = {"topic", "research_goal", "key_insights", "decision_patterns", "barriers", "action_suggestions", "evidence_trace"}
    return isinstance(obj, dict) and required.issubset(set(obj.keys()))


def validate_topic_report_json(obj: Any) -> bool:
    required = {
        "topic",
        "research_goal",
        "executive_summary",
        "population_patterns",
        "segment_differences",
        "key_risks",
        "actionable_recommendations",
        "further_questions",
        "evidence_trace",
        "confidence_notes",
    }
    return isinstance(obj, dict) and required.issubset(set(obj.keys()))


def validate_aggregate_results_json(obj: Any) -> bool:
    required = {"topic", "sample_overview", "common_patterns", "differences", "risks", "recommendations"}
    return isinstance(obj, dict) and required.issubset(set(obj.keys()))


def validate_professional_report_json(obj: Any) -> bool:
    required = {"topic", "executive_summary", "methodology", "sample_profile", "key_findings", "theme_analysis", "population_segments", "recommendations", "limitations"}
    return isinstance(obj, dict) and required.issubset(set(obj.keys()))


def request_json_with_retry(
    model_cfg: ModelConfig,
    messages: List[Dict[str, str]],
    validator: Callable[[Any], bool],
    max_retries: int = 3,
) -> Any:
    last_obj = None
    retry_messages = list(messages)
    for idx in range(max_retries):
        raw = call_llm_with_retry(model_cfg, retry_messages, max_retries=1)
        try:
            obj = extract_json(raw)
            last_obj = obj
            if validator(obj):
                return obj
        except Exception:
            pass
        if idx < max_retries - 1:
            retry_messages = retry_messages + [{
                "role": "user",
                "content": "上一个输出不符合JSON schema，请仅返回严格JSON，字段齐全且类型正确，不要附加解释。",
            }]
    raise ValueError(f"JSON schema validation failed after retries: {last_obj}")
