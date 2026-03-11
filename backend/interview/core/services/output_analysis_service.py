from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from ..io.output_store import OutputStore


class OutputAnalysisService:
    def __init__(self, store: OutputStore):
        self.store = store

    def analyze_outputs(self) -> Dict[str, Any]:
        score_rows = self.store.read_score_records()
        convo_rows = self.store.read_conversation_records()
        by_model = defaultdict(list)
        by_survey = defaultdict(list)
        turns_by_model = defaultdict(list)
        for row in score_rows:
            model = row.get("interviewer_model") or row.get("model_name") or "unknown"
            survey = row.get("survey_name") or "unknown"
            score_obj = row.get("score", {})
            score_value = score_obj.get("score") if isinstance(score_obj, dict) else None
            if score_value is not None:
                by_model[model].append(float(score_value))
                by_survey[survey].append(float(score_value))
        convo_by_key = {(row.get("benchmark_dir"), row.get("interviewer_model")): row for row in convo_rows}
        for row in score_rows:
            key = (row.get("benchmark_dir"), row.get("interviewer_model"))
            convo = convo_by_key.get(key)
            if convo:
                model = row.get("interviewer_model") or row.get("model_name") or "unknown"
                turns = convo.get("used_turns") or convo.get("turn_count")
                if turns is not None:
                    turns_by_model[model].append(float(turns))
        return {
            "total_score_records": len(score_rows),
            "total_conversation_records": len(convo_rows),
            "by_model": {k: {"count": len(v), "avg_score": round(sum(v) / len(v), 4) if v else 0.0} for k, v in by_model.items()},
            "by_survey": {k: {"count": len(v), "avg_score": round(sum(v) / len(v), 4) if v else 0.0} for k, v in by_survey.items()},
            "avg_turns_by_model": {k: round(sum(v) / len(v), 2) if v else 0.0 for k, v in turns_by_model.items()},
        }

    def compare_models_by_survey(self) -> List[Dict[str, Any]]:
        score_rows = self.store.read_score_records()
        grouped = defaultdict(list)
        for row in score_rows:
            survey = row.get("survey_name") or "unknown"
            model = row.get("interviewer_model") or row.get("model_name") or "unknown"
            score_obj = row.get("score", {})
            score_value = score_obj.get("score") if isinstance(score_obj, dict) else None
            if score_value is not None:
                grouped[(survey, model)].append(float(score_value))
        results: Dict[str, Dict[str, Any]] = defaultdict(dict)
        for (survey, model), values in grouped.items():
            results[survey][model] = round(sum(values) / len(values), 4)
        output = []
        for survey, model_scores in results.items():
            sorted_scores = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)
            gap = round(sorted_scores[0][1] - sorted_scores[-1][1], 4) if len(sorted_scores) >= 2 else 0.0
            output.append({"survey_name": survey, "model_scores": model_scores, "score_gap": gap})
        return sorted(output, key=lambda x: x["score_gap"], reverse=True)

    def find_representative_cases(self, top_k: int = 5, require_events: bool = True) -> List[Dict[str, Any]]:
        score_rows = self.store.read_score_records()
        convo_rows = self.store.read_conversation_records()
        convo_index = {(row.get("benchmark_dir"), row.get("interviewer_model")): row for row in convo_rows}
        candidates: List[Dict[str, Any]] = []
        for row in score_rows:
            key = (row.get("benchmark_dir"), row.get("interviewer_model"))
            convo = convo_index.get(key, {})
            event_count = convo.get("event_count", convo.get("event_total", 0))
            if require_events and event_count <= 0:
                continue
            score_obj = row.get("score", {})
            score_value = score_obj.get("score") if isinstance(score_obj, dict) else None
            candidates.append(
                {
                    "benchmark_dir": row.get("benchmark_dir"),
                    "model_name": row.get("interviewer_model") or row.get("model_name"),
                    "survey_name": row.get("survey_name"),
                    "score": score_value,
                    "event_count": event_count,
                    "turn_count": convo.get("turn_count", convo.get("used_turns")),
                }
            )
        candidates.sort(key=lambda x: ((x.get("score") or 0), (x.get("event_count") or 0)), reverse=True)
        return candidates[:top_k]
