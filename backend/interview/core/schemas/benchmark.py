from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BenchmarkMeta:
    survey_name: str = ""
    dataset_name: Optional[str] = None
    respondent_id: Optional[str] = None
    questionnaire_path: Optional[str] = None
    sample_path: Optional[str] = None
    sample_index: Optional[int] = None
    seed: Optional[int] = None
    scenario_profile: Optional[str] = None
    source_mode: Optional[str] = None
    source_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PersonaProfile:
    persona_profile: str = ""
    persona_facts: List[str] = field(default_factory=list)
    persona_traits: Dict[str, Any] = field(default_factory=dict)
    answer_memory: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioEvent:
    event_type: str = "none"
    event_description: str = "无异常"
    event_emotion: str = "平静"
    event_intensity: str = "轻微"
    event_expression: str = "直接表达"
    question_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioPlan:
    events: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {str(k): v for k, v in self.events.items()}


@dataclass
class BenchmarkCase:
    benchmark_dir: Optional[str] = None
    questionnaire: Dict[str, Any] = field(default_factory=dict)
    ground_truth: Dict[str, Any] = field(default_factory=dict)
    persona: Dict[str, Any] = field(default_factory=dict)
    scenario_plan: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
    mapping: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_dir": self.benchmark_dir,
            "questionnaire": self.questionnaire,
            "ground_truth": self.ground_truth,
            "persona": self.persona,
            "scenario_plan": {str(k): v for k, v in self.scenario_plan.items()},
            "meta": self.meta,
            "mapping": self.mapping,
        }
