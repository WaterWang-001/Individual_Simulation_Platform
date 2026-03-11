from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from event_library import EVENT_INTENSITY, EXPRESSION_STYLE, UNEXPECTED_EVENTS

from ..io.file_store import load_json


BASE_DIR = Path(__file__).resolve().parents[2]
EVENT_PROB_PATH = BASE_DIR / "event_probabilities.json"


class ScenarioPlanner:
    @staticmethod
    def load_event_probabilities() -> Dict[str, Any]:
        if EVENT_PROB_PATH.exists():
            return load_json(EVENT_PROB_PATH)
        return {
            "default_none_weight": 10,
            "default_event_weight": 2,
            "event_type_weights": {},
            "question_type_weights": {},
        }

    @classmethod
    def generate_scenario_plan(
        cls,
        questionnaire: Dict[str, Any],
        seed: int,
        scenario_profile: str = "mixed",
        force_required_events: Optional[bool] = None,
    ) -> Dict[int, Dict[str, str]]:
        rng = random.Random(seed)
        plan: Dict[int, Dict[str, str]] = {}
        events = UNEXPECTED_EVENTS[:] or [{"event_type": "none", "description": "无异常", "possible_emotions": ["平静"]}]
        prob_cfg = cls.load_event_probabilities()
        none_weight = int(prob_cfg.get("default_none_weight", 10))
        base_event_weight = int(prob_cfg.get("default_event_weight", 2))
        if scenario_profile == "clean":
            none_weight = max(50, none_weight * 3)
            base_event_weight = 1
        event_type_weights = prob_cfg.get("event_type_weights", {})
        type_weights = prob_cfg.get("question_type_weights", {})

        def build_pool(qtype: str) -> List[Dict[str, Any]]:
            pool = [{"event_type": "none", "description": "无异常", "possible_emotions": ["平静"]}] * max(1, none_weight)
            for event in events:
                if event.get("event_type") == "none":
                    continue
                qtypes = event.get("question_types")
                if qtypes is not None and qtype not in qtypes:
                    continue
                weight = base_event_weight
                weight += int(event_type_weights.get(event.get("event_type"), 0))
                weight += int(type_weights.get(qtype, {}).get(event.get("event_type"), 0))
                pool.extend([event] * max(1, weight))
            return pool

        qmap = {int(q["id"]): q for q in questionnaire.get("questions", [])}
        for qid, question in qmap.items():
            qtype = question.get("type")
            event = rng.choice(build_pool(qtype))
            plan[qid] = {
                "event_type": event["event_type"],
                "event_description": event["description"],
                "event_emotion": rng.choice(event.get("possible_emotions", ["平静"])),
                "event_intensity": rng.choice(EVENT_INTENSITY),
                "event_expression": rng.choice(EXPRESSION_STYLE),
                "question_type": qtype,
            }

        if force_required_events is None:
            force_required_events = scenario_profile != "clean"
        if force_required_events:
            required = [
                "topic_derailment",
                "topic_refusal",
                "contradictory_information",
                "question_misunderstanding",
                "memory_failure",
                "passive_noncooperation",
                "questionnaire_critique",
                "early_termination_request",
            ]
            for qid, event_type in zip(sorted(qmap.keys()), required):
                for event in events:
                    if event["event_type"] == event_type:
                        plan[qid] = {
                            "event_type": event["event_type"],
                            "event_description": event["description"],
                            "event_emotion": rng.choice(event.get("possible_emotions", ["平静"])),
                            "event_intensity": rng.choice(EVENT_INTENSITY),
                            "event_expression": rng.choice(EXPRESSION_STYLE),
                            "question_type": qmap[qid].get("type"),
                        }
                        break
        return plan
