from __future__ import annotations

from typing import Any, Dict, List


class ProcessEvaluator:
    def evaluate(self, questionnaire: Dict[str, Any], history: List[Dict[str, str]], decisions: List[Dict[str, Any]], event_total: int, used_turns: int) -> Dict[str, Any]:
        total_questions = len(questionnaire.get("questions", []))
        answered_turns = 0
        refusal_count = 0
        recovery_count = 0
        response_lengths: List[int] = []
        for decision in decisions:
            action = decision.get("action")
            event = (decision.get("event") or {}).get("event_type")
            if action in ["ask_question", "follow_up", "clarify"] and event not in ["topic_refusal", "sensitive_topic_resistance", "passive_noncooperation"]:
                answered_turns += 1
            if event in ["topic_refusal", "sensitive_topic_resistance", "passive_noncooperation"]:
                refusal_count += 1
        last_refusal_qid: Dict[int, int] = {}
        for idx, decision in enumerate(decisions):
            qid = decision.get("target_question_id")
            if qid is None:
                continue
            event = (decision.get("event") or {}).get("event_type")
            if event in ["topic_refusal", "sensitive_topic_resistance", "passive_noncooperation"]:
                last_refusal_qid[int(qid)] = idx
            elif event and event != "none":
                continue
            elif int(qid) in last_refusal_qid:
                recovery_count += 1
                del last_refusal_qid[int(qid)]
        for message in history:
            if message.get("role") == "interviewee":
                text = (message.get("content") or "").strip()
                if text:
                    response_lengths.append(len(text))
        avg_resp_len = round(sum(response_lengths) / len(response_lengths), 2) if response_lengths else 0.0
        return {
            "info_coverage_proxy": round(answered_turns / max(1, total_questions), 4),
            "flow_efficiency": round(answered_turns / max(1, used_turns), 4),
            "avg_interviewee_response_len": avg_resp_len,
            "refusal_recovery_rate": round(recovery_count / max(1, refusal_count), 4),
            "event_rate_per_turn": round(event_total / max(1, used_turns), 4),
        }
