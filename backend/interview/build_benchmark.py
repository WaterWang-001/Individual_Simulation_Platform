import json
import os
from pathlib import Path
from typing import Dict

from config import project_model_config_candidates
from core.io.file_store import load_json, load_jsonl
from core.schemas.common import ModelConfig
from core.services.benchmark_builder import BenchmarkBuilder
from core.services.source_bundle_service import SourceBundleService

BASE_DIR = Path(__file__).resolve().parent
SOURCE_BUNDLE_DIR = os.path.join(str(BASE_DIR), "benchmark_sources")


def load_persona_model_config(config_path: str, model_name: str = "qwen3-max") -> ModelConfig:
    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    for item in raw.get("models", []):
        if item.get("name") == model_name:
            return ModelConfig.from_dict(item)
    raise ValueError(f"{model_name} not found in {os.path.basename(config_path)}")


if __name__ == "__main__":
    candidates = project_model_config_candidates(BASE_DIR, "./project_config.json")
    config_path = str(next((path for path in candidates if path.exists()), candidates[0]))
    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "models": [
                        {"name": "qwen3-max", "api_key_env": "DASHSCOPE_API_KEY", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
                        {"name": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com"},
                        {"name": "gpt-4o", "api_key_env": "OPENAI_API_KEY", "base_url": "https://api.openai.com/v1"},
                    ]
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    persona_model_cfg = load_persona_model_config(config_path, model_name="qwen3-max")
    scenario_profiles = [item.strip() for item in os.environ.get("SCENARIO_PROFILES", "mixed,clean").split(",") if item.strip()]
    if not scenario_profiles:
        scenario_profiles = ["mixed"]

    bundles = SourceBundleService.discover_source_bundles(SOURCE_BUNDLE_DIR)
    if not bundles:
        from prepare_benchmark_sources import main as prepare_sources_main

        prepare_sources_main()
        bundles = SourceBundleService.discover_source_bundles(SOURCE_BUNDLE_DIR)
    if not bundles:
        raise ValueError(f"No source bundles found under {SOURCE_BUNDLE_DIR}")

    sample_limit = max(1, int(os.environ.get("SAMPLES_PER_DATASET", "2")))
    builder = BenchmarkBuilder(persona_model_cfg)

    for bundle in bundles:
        dataset_name = bundle["dataset_name"]
        questionnaire_template = load_json(bundle["template_path"])
        records = load_jsonl(bundle["records_path"])
        take_n = min(sample_limit, len(records))
        survey_slug = builder.safe_slug(questionnaire_template.get("survey_name"))
        for i in range(take_n):
            record = records[i]
            respondent_id = str(record.get("respondent_id", i + 1))
            questionnaire_with_answers = record.get("questionnaire_with_answers", {})
            for profile in scenario_profiles:
                suffix = "" if profile == "mixed" else f"_{profile}"
                out_dir = os.path.join(str(BASE_DIR), "benchmarks", f"{dataset_name}_{survey_slug}_{i + 1:03d}{suffix}")
                builder.build_from_record(
                    out_dir=out_dir,
                    questionnaire_template=questionnaire_template,
                    questionnaire_with_answers=questionnaire_with_answers,
                    respondent_id=respondent_id,
                    dataset_name=dataset_name,
                    seed=20240202 + i,
                    scenario_profile=profile,
                )
