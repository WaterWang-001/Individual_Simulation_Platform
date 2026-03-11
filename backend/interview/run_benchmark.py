import json
import os
from pathlib import Path
from typing import Dict

from config import project_model_config_candidates
from core.io.output_store import OutputStore
from core.orchestrators.interview_orchestrator import InterviewOrchestrator
from core.schemas.common import ModelConfig
from core.services.agents.final_profiler import FinalProfiler
from core.services.agents.interviewee_agent import IntervieweeAgent
from core.services.agents.interviewer_agent import InterviewerAgent
from core.services.agents.questionnaire_filler import QuestionnaireFiller
from core.services.agents.questionnaire_summarizer import QuestionnaireSummarizer
from core.services.evaluation.process_evaluator import ProcessEvaluator
from core.services.evaluation.recovery_policy_engine import RecoveryPolicyEngine
from core.services.evaluation.scorer import Scorer
from core.services.evaluation.stage_planner import StagePlanner

BASE_DIR = Path(__file__).resolve().parent


def resolve_runtime_config_path() -> str:
    candidates = project_model_config_candidates(BASE_DIR, "./project_config.json")
    for path in candidates:
        if path.exists():
            return str(path)
    return str(candidates[-1])


def load_config(config_path: str) -> Dict[str, ModelConfig]:
    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    models: Dict[str, ModelConfig] = {}
    for item in raw.get("models", []):
        cfg = ModelConfig.from_dict(item)
        models[cfg.name] = cfg
    return models


class BenchmarkRunner:
    def __init__(self, config: Dict[str, ModelConfig]):
        self.config = config
        self.orchestrator = InterviewOrchestrator(config)

    def run_once(
        self,
        benchmark_dir: str,
        interviewer_model: str,
        interviewee_model: str,
        output_dir: str,
        max_turns_multiplier: int = 3,
        handling_mode: str = "default",
        ablation_mode: str = "direct",
        compare_fill_modes: bool = False,
        no_event_mode: bool = True,
        event_trigger_prob: float = 0.0,
        free_chat_turn_limit: int = 2,
    ) -> None:
        result = self.orchestrator.run(
            benchmark_dir=benchmark_dir,
            interviewer_model=interviewer_model,
            interviewee_model=interviewee_model,
            max_turns_multiplier=max_turns_multiplier,
            handling_mode=handling_mode,
            ablation_mode=ablation_mode,
            compare_fill_modes=compare_fill_modes,
            no_event_mode=no_event_mode,
            event_trigger_prob=event_trigger_prob,
            free_chat_turn_limit=free_chat_turn_limit,
        )
        store = OutputStore(output_dir)
        store.append_conversation_record(result.conversation_record)
        store.append_questionnaire_record(result.questionnaire_record)
        store.append_score_record(result.score_record)


if __name__ == "__main__":
    config_path = resolve_runtime_config_path()
    models = load_config(config_path)
    runner = BenchmarkRunner(models)
    runner.run_once(
        benchmark_dir=os.path.join(str(BASE_DIR), "benchmarks", "经济调查_survey_635a70b5_001_clean"),
        interviewer_model="qwen3-max",
        interviewee_model="qwen3-max",
        output_dir=os.path.join(str(BASE_DIR), "outputs"),
    )
