from __future__ import annotations

from typing import Any, Dict


class RecoveryPolicyEngine:
    def __init__(self):
        self.policy_by_event = {
            "topic_refusal": ("resistance", "resistance_softened", "acknowledge_rephrase_then_defer", "partial_answer", 2),
            "sensitive_topic_resistance": ("resistance", "deferred", "privacy_respect_and_skip", "safe_alternative", 1),
            "passive_noncooperation": ("low_engagement", "engagement_recovered", "short_question_with_example", "minimum_fact", 2),
            "question_misunderstanding": ("misunderstood", "clarified", "rephrase_and_verify", "accurate_interpretation", 2),
            "contradictory_information": ("inconsistent", "partially_consistent", "timeline_clarification", "single_consistent_claim", 2),
            "memory_failure": ("memory_gap", "memory_supported", "time_anchor_prompt", "approximate_answer", 2),
            "emotional_breakdown": ("emotional", "stabilized", "empathy_then_optional_continue", "safe_short_answer", 2),
            "early_termination_request": ("termination_risk", "deescalated", "offer_quick_finish_or_pause", "one_key_answer", 1),
            "questionnaire_critique": ("friction", "friction_reduced", "explain_value_and_offer_skip", "cooperative_response", 1),
        }

    def apply(self, qid: int, event: Dict[str, Any], sufficient: bool, state_tracker: Dict[int, str]) -> Dict[str, Any]:
        event_type = (event or {}).get("event_type", "none")
        state_before = state_tracker.get(qid, "normal")
        if event_type in self.policy_by_event:
            default_before, default_after, policy, target, max_turns = self.policy_by_event[event_type]
            if state_before == "normal":
                state_before = default_before
            state_after = "recovered" if sufficient else default_after
            if event_type == "sensitive_topic_resistance" and not sufficient:
                state_after = "deferred"
            result = {
                "state_before": state_before,
                "state_after": state_after,
                "policy_applied": policy,
                "recovery_target": target,
                "max_recovery_turns": max_turns,
            }
        else:
            result = {
                "state_before": state_before,
                "state_after": "normal" if sufficient else "needs_followup",
                "policy_applied": "none",
                "recovery_target": "normal_progress",
                "max_recovery_turns": 0,
            }
        state_tracker[qid] = result["state_after"]
        return result
