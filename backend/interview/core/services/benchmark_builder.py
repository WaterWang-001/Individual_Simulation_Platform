from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from ..io.file_store import write_json
from ..schemas.common import ModelConfig
from .ground_truth_builder import GroundTruthBuilder
from .persona_builder import PersonaBuilder
from .scenario_planner import ScenarioPlanner


class BenchmarkBuilder:
    def __init__(self, persona_model_cfg: ModelConfig):
        self.persona_model_cfg = persona_model_cfg

    @staticmethod
    def safe_slug(text: str) -> str:
        if not text:
            return "survey"
        import re
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
        if cleaned:
            return cleaned.lower()
        digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
        return f"survey_{digest}"

    def build_from_mapping_sample(
        self,
        out_dir: str | Path,
        questionnaire: Dict[str, Any],
        raw_sample: Dict[str, Any],
        mapping: Optional[Dict[str, Any]],
        questionnaire_path: str,
        sample_path: str,
        sample_index: int,
        seed: int = 42,
        scenario_profile: str = "mixed",
    ) -> str:
        out_dir = str(out_dir)
        if mapping is None:
            mapping = {
                "survey_name": questionnaire.get("survey_name"),
                "questionnaire_path": questionnaire_path,
                "sample_path": sample_path,
                "field_map": GroundTruthBuilder.infer_field_map(questionnaire, raw_sample),
            }
        ground_truth = GroundTruthBuilder.build_ground_truth(questionnaire, raw_sample, mapping)
        persona = PersonaBuilder.generate_persona(self.persona_model_cfg, ground_truth)
        scenario_plan = ScenarioPlanner.generate_scenario_plan(questionnaire, seed, scenario_profile=scenario_profile)
        write_json(Path(out_dir) / "questionnaire.json", questionnaire)
        write_json(Path(out_dir) / "ground_truth.json", ground_truth)
        write_json(Path(out_dir) / "mapping.json", mapping)
        write_json(Path(out_dir) / "persona.json", persona)
        write_json(Path(out_dir) / "scenario_plan.json", {str(k): v for k, v in scenario_plan.items()})
        write_json(Path(out_dir) / "meta.json", {
            "questionnaire_path": questionnaire_path,
            "sample_path": sample_path,
            "sample_index": sample_index,
            "survey_name": questionnaire.get("survey_name"),
            "seed": seed,
            "scenario_profile": scenario_profile,
        })
        return out_dir

    def build_from_record(
        self,
        out_dir: str | Path,
        questionnaire_template: Dict[str, Any],
        questionnaire_with_answers: Dict[str, Any],
        respondent_id: str,
        dataset_name: str,
        seed: int = 42,
        scenario_profile: str = "mixed",
    ) -> str:
        out_dir = str(out_dir)
        questionnaire = GroundTruthBuilder.strip_answers(questionnaire_template)
        ground_truth = GroundTruthBuilder.questionnaire_to_ground_truth(questionnaire_with_answers)
        persona = PersonaBuilder.generate_persona(self.persona_model_cfg, ground_truth)
        scenario_plan = ScenarioPlanner.generate_scenario_plan(questionnaire, seed, scenario_profile=scenario_profile)
        write_json(Path(out_dir) / "questionnaire.json", questionnaire)
        write_json(Path(out_dir) / "ground_truth.json", ground_truth)
        write_json(Path(out_dir) / "persona.json", persona)
        write_json(Path(out_dir) / "scenario_plan.json", {str(k): v for k, v in scenario_plan.items()})
        write_json(Path(out_dir) / "meta.json", {
            "dataset_name": dataset_name,
            "respondent_id": respondent_id,
            "survey_name": questionnaire.get("survey_name"),
            "seed": seed,
            "scenario_profile": scenario_profile,
            "source_mode": "prepared_source_bundle",
            "source_name": dataset_name,
        })
        return out_dir
