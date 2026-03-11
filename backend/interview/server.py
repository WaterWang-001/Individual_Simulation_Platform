from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

PLUGIN_ROOT = Path(__file__).resolve().parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

try:
    from fastmcp import FastMCP
except ImportError:
    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, name: str):
            self.name = name

        def tool(self, *_args: Any, **_kwargs: Any):
            def decorator(func):
                return func
            return decorator

        def run(self) -> None:
            raise SystemExit("fastmcp 未安装，请先执行: pip install -r requirements.txt")

from config import load_plugin_config
from paths import resolve_paths
from toolkit import PluginToolkit

CONFIG = load_plugin_config(PLUGIN_ROOT)
PATHS = resolve_paths(PLUGIN_ROOT, CONFIG)
TOOLKIT = PluginToolkit(CONFIG, PATHS)

mcp = FastMCP(CONFIG.server_name)


@mcp.tool()
def get_project_map() -> Dict[str, Any]:
    return TOOLKIT.get_project_map()


@mcp.tool()
def project_overview() -> Dict[str, Any]:
    return TOOLKIT.get_project_map()


@mcp.tool()
def list_prompt_templates() -> Dict[str, Any]:
    return TOOLKIT.list_prompt_templates()


@mcp.tool()
def create_interview_task(
    topic: str,
    target_population: str,
    research_goal: str,
    survey: Optional[Dict[str, Any]] = None,
    sample_size: int = 5,
    report_style: str = "professional",
    constraints: Optional[Dict[str, Any]] = None,
    user_need: str = "",
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.create_interview_task(
        topic=topic,
        target_population=target_population,
        research_goal=research_goal,
        survey=survey,
        sample_size=sample_size,
        report_style=report_style,
        constraints=constraints,
        user_need=user_need,
        model_name=model_name,
    )


@mcp.tool()
def generate_candidate_personas(
    task: Dict[str, Any],
    persona_pool: Optional[List[Dict[str, Any]]] = None,
    diversity_requirements: Optional[List[str]] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.generate_candidate_personas(
        task=task,
        persona_pool=persona_pool,
        diversity_requirements=diversity_requirements,
        model_name=model_name,
    )


@mcp.tool()
def review_persona_pool(
    task: Dict[str, Any],
    personas: List[Dict[str, Any]],
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.review_persona_pool(task=task, personas=personas, model_name=model_name)


@mcp.tool()
def generate_interview_plan(task: Dict[str, Any], model_name: Optional[str] = None) -> Dict[str, Any]:
    return TOOLKIT.generate_interview_plan(task=task, model_name=model_name)


@mcp.tool()
def generate_interview_outline(
    topic: str,
    research_goal: str = "",
    target_population: str = "",
    user_need: str = "",
    interview_style: str = "semi_structured",
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.generate_interview_outline(
        topic=topic,
        research_goal=research_goal,
        target_population=target_population,
        user_need=user_need,
        interview_style=interview_style,
        model_name=model_name,
    )


@mcp.tool()
def plan_interview_stage(
    task: Dict[str, Any],
    plan: Dict[str, Any],
    history: Optional[List[Dict[str, Any]]] = None,
    filled_slots: Optional[Dict[str, Any]] = None,
    answered_ids: Optional[List[int]] = None,
    used_turns: int = 0,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.plan_interview_stage(
        task=task,
        plan=plan,
        history=history,
        filled_slots=filled_slots,
        answered_ids=answered_ids,
        used_turns=used_turns,
        model_name=model_name,
    )


@mcp.tool()
def draft_next_question(
    task: Dict[str, Any],
    plan: Dict[str, Any],
    persona: Dict[str, Any],
    history: List[Dict[str, Any]],
    filled_slots: Optional[Dict[str, Any]] = None,
    answered_ids: Optional[List[int]] = None,
    skipped_ids: Optional[List[int]] = None,
    used_turns: int = 0,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.draft_next_question(
        task=task,
        plan=plan,
        persona=persona,
        history=history,
        filled_slots=filled_slots,
        answered_ids=answered_ids,
        skipped_ids=skipped_ids,
        used_turns=used_turns,
        model_name=model_name,
    )


@mcp.tool()
def simulate_interviewee_reply(
    task: Dict[str, Any],
    persona: Dict[str, Any],
    question: Dict[str, Any],
    history: List[Dict[str, Any]],
    stage_context: Optional[Dict[str, Any]] = None,
    event_policy: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.simulate_interviewee_reply(
        task=task,
        persona=persona,
        question=question,
        history=history,
        stage_context=stage_context,
        event_policy=event_policy,
        model_name=model_name,
    )


@mcp.tool()
def run_single_interview(
    task: Dict[str, Any],
    persona: Dict[str, Any],
    plan: Dict[str, Any],
    interviewer_model: Optional[str] = None,
    interviewee_model: Optional[str] = None,
    event_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return TOOLKIT.run_single_interview(
        task=task,
        persona=persona,
        plan=plan,
        interviewer_model=interviewer_model,
        interviewee_model=interviewee_model,
        event_policy=event_policy,
    )


@mcp.tool()
def fill_questionnaire_from_history(
    task: Dict[str, Any],
    plan: Dict[str, Any],
    history: List[Dict[str, Any]],
    filled_slots: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.fill_questionnaire_from_history(
        task=task,
        plan=plan,
        history=history,
        filled_slots=filled_slots,
        model_name=model_name,
    )


@mcp.tool()
def summarize_individual_interview(
    task: Dict[str, Any],
    persona: Dict[str, Any],
    history: List[Dict[str, Any]],
    filled_questionnaire: Dict[str, Any],
    user_need: str = "",
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.summarize_individual_interview(
        task=task,
        persona=persona,
        history=history,
        filled_questionnaire=filled_questionnaire,
        user_need=user_need,
        model_name=model_name,
    )


@mcp.tool()
def extract_research_insights_from_interview(
    task: Dict[str, Any],
    persona: Dict[str, Any],
    history: List[Dict[str, Any]],
    filled_questionnaire: Dict[str, Any],
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.extract_research_insights_from_interview(
        task=task,
        persona=persona,
        history=history,
        filled_questionnaire=filled_questionnaire,
        model_name=model_name,
    )


@mcp.tool()
def aggregate_interview_results(
    task: Dict[str, Any],
    interview_results: List[Dict[str, Any]],
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.aggregate_interview_results(task=task, interview_results=interview_results, model_name=model_name)


@mcp.tool()
def generate_professional_report(
    task: Dict[str, Any],
    personas: List[Dict[str, Any]],
    interview_results: List[Dict[str, Any]],
    aggregation: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    return TOOLKIT.generate_professional_report(
        task=task,
        personas=personas,
        interview_results=interview_results,
        aggregation=aggregation,
        model_name=model_name,
    )


@mcp.tool()
def score_questionnaire(questionnaire: Dict[str, Any], filled_questionnaire: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, Any]:
    return TOOLKIT.score_questionnaire(questionnaire=questionnaire, filled_questionnaire=filled_questionnaire, ground_truth=ground_truth)


@mcp.tool()
def build_persona_from_answers(answers: Dict[str, Any], model_name: Optional[str] = None) -> Dict[str, Any]:
    return TOOLKIT.build_persona_from_answers(answers=answers, model_name=model_name)


@mcp.tool()
def legacy_list_benchmark_cases(clean_only: bool = True) -> Dict[str, Any]:
    return TOOLKIT.legacy_list_benchmark_cases(clean_only=clean_only)


@mcp.tool()
def legacy_read_benchmark_case(case_id: str) -> Dict[str, Any]:
    return TOOLKIT.legacy_read_benchmark_case(case_id=case_id)


@mcp.tool()
def legacy_analyze_outputs() -> Dict[str, Any]:
    return TOOLKIT.legacy_analyze_outputs()


@mcp.tool()
def legacy_compare_models_by_survey() -> Dict[str, Any]:
    return TOOLKIT.legacy_compare_models_by_survey()


@mcp.tool()
def legacy_find_representative_cases(top_k: int = 5, require_events: bool = True) -> Dict[str, Any]:
    return TOOLKIT.legacy_find_representative_cases(top_k=top_k, require_events=require_events)


@mcp.tool()
def legacy_read_output_record(record_type: str, benchmark_dir: Optional[str] = None, model_name: Optional[str] = None) -> Dict[str, Any]:
    return TOOLKIT.legacy_read_output_record(record_type=record_type, benchmark_dir=benchmark_dir, model_name=model_name)


if __name__ == "__main__":
    mcp.run()
