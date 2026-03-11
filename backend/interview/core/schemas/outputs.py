from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .common import ErrorRecord, WarningRecord


@dataclass
class QuestionnaireFillResult:
    questionnaire: Dict[str, Any] = field(default_factory=dict)
    questionnaire_direct: Optional[Dict[str, Any]] = None
    questionnaire_summary_mode: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScoreDetail:
    id: int
    type: str
    ground_truth: Any
    pred: Any
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScoreReport:
    total: int = 0
    score: float = 0.0
    details: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessMetrics:
    info_coverage_proxy: float = 0.0
    flow_efficiency: float = 0.0
    avg_interviewee_response_len: float = 0.0
    refusal_recovery_rate: float = 0.0
    event_rate_per_turn: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FinalProfile:
    profile_summary: str = ""
    questionnaire_traits: List[Any] = field(default_factory=list)
    general_personality_traits: List[Any] = field(default_factory=list)
    communication_style: List[Any] = field(default_factory=list)
    consistency_and_conflicts: List[Any] = field(default_factory=list)
    risk_signals: List[Any] = field(default_factory=list)
    insights: List[Any] = field(default_factory=list)
    next_interview_suggestions: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunResult:
    conversation_record: Dict[str, Any]
    questionnaire_record: Dict[str, Any]
    score_record: Dict[str, Any]
    final_profile: Dict[str, Any] = field(default_factory=dict)
    process_metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[WarningRecord] = field(default_factory=list)
    errors: List[ErrorRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_record": self.conversation_record,
            "questionnaire_record": self.questionnaire_record,
            "score_record": self.score_record,
            "final_profile": self.final_profile,
            "process_metrics": self.process_metrics,
            "warnings": [w.to_dict() for w in self.warnings],
            "errors": [e.to_dict() for e in self.errors],
        }
