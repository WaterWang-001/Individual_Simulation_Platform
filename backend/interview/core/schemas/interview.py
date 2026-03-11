from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InterviewStage:
    stage_name: str
    stage_goal: str
    stage_candidates: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InterviewAction:
    action: str
    target_question_id: Optional[int]
    reason_tag: str
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InterviewTurn:
    turn: int
    stage: str
    action: str
    target_question_id: Optional[int]
    reason_tag: str = ""
    note: str = ""
    event: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecoveryRecord:
    state_before: str = "normal"
    state_after: str = "normal"
    policy_applied: str = "none"
    recovery_target: str = "normal_progress"
    max_recovery_turns: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InterviewState:
    history: List[Dict[str, str]] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    process_logs: List[Dict[str, Any]] = field(default_factory=list)
    answered_ids: List[int] = field(default_factory=list)
    skipped_ids: List[int] = field(default_factory=list)
    deferred_ids: List[int] = field(default_factory=list)
    attempt_counter: Dict[int, int] = field(default_factory=dict)
    state_tracker: Dict[int, str] = field(default_factory=dict)
    used_turns: int = 0
    free_chat_used: int = 0
    plan_used: int = 0
    event_counts: Dict[str, int] = field(default_factory=dict)
    event_total: int = 0
    terminated_reason: str = "normal"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
