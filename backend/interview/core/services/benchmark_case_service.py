from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ..io.file_store import load_json
from ..schemas.benchmark import BenchmarkCase


class BenchmarkCaseService:
    def __init__(self, benchmarks_dir: str | Path):
        self.benchmarks_dir = Path(benchmarks_dir)

    def list_cases(self, clean_only: bool = True) -> List[Dict[str, Any]]:
        if not self.benchmarks_dir.exists():
            return []
        items: List[Dict[str, Any]] = []
        for case_dir in sorted([p for p in self.benchmarks_dir.iterdir() if p.is_dir()]):
            if clean_only and not case_dir.name.endswith("_clean"):
                continue
            meta = load_json(case_dir / "meta.json") if (case_dir / "meta.json").exists() else {}
            items.append(
                {
                    "case_id": case_dir.name,
                    "path": str(case_dir),
                    "survey_name": meta.get("survey_name", case_dir.name),
                    "source_name": meta.get("source_name"),
                    "has_mapping": (case_dir / "mapping.json").exists(),
                    "has_persona": (case_dir / "persona.json").exists(),
                    "has_scenario_plan": (case_dir / "scenario_plan.json").exists(),
                }
            )
        return items

    def read_case(self, case_id: str) -> BenchmarkCase | None:
        case_dir = self.benchmarks_dir / case_id
        if not case_dir.exists():
            return None
        scenario_plan = load_json(case_dir / "scenario_plan.json") if (case_dir / "scenario_plan.json").exists() else {}
        scenario_plan = {int(k): v for k, v in scenario_plan.items()}
        return BenchmarkCase(
            benchmark_dir=str(case_dir),
            questionnaire=load_json(case_dir / "questionnaire.json") if (case_dir / "questionnaire.json").exists() else {},
            ground_truth=load_json(case_dir / "ground_truth.json") if (case_dir / "ground_truth.json").exists() else {},
            persona=load_json(case_dir / "persona.json") if (case_dir / "persona.json").exists() else {},
            scenario_plan=scenario_plan,
            meta=load_json(case_dir / "meta.json") if (case_dir / "meta.json").exists() else {},
            mapping=load_json(case_dir / "mapping.json") if (case_dir / "mapping.json").exists() else None,
        )
