import json
import os
from collections import defaultdict
from typing import Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs_02")
SUMMARY_PATH = os.path.join(OUTPUT_DIR, "summary_existing_outputs.json")


def load_jsonl(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def summarize_scores(score_records: List[Dict]) -> Dict:
    by_model = defaultdict(list)
    by_survey = defaultdict(list)
    by_model_survey = defaultdict(list)
    by_mode = defaultdict(list)
    by_model_mode = defaultdict(list)
    by_survey_mode = defaultdict(list)

    for item in score_records:
        model = item.get("interviewer_model")
        survey = item.get("survey_name")
        handling_mode = item.get("handling_mode", "default")
        ablation_mode = item.get("ablation_mode", "direct")
        mode = f"{handling_mode}::{ablation_mode}"
        score = item.get("score", {}).get("score")
        if model is None or score is None:
            continue
        score = float(score)
        by_model[model].append(score)
        if survey:
            by_survey[survey].append(score)
            by_model_survey[(model, survey)].append(score)
        by_mode[mode].append(score)
        by_model_mode[(model, mode)].append(score)
        if survey:
            by_survey_mode[(survey, mode)].append(score)

    def avg(xs: List[float]) -> float:
        return round(sum(xs) / len(xs), 4) if xs else 0.0

    return {
        "total_records": len(score_records),
        "by_model": {m: {"count": len(xs), "avg_score": avg(xs)} for m, xs in by_model.items()},
        "by_survey": {s: {"count": len(xs), "avg_score": avg(xs)} for s, xs in by_survey.items()},
        "by_model_survey": {
            f"{m}::{s}": {"count": len(xs), "avg_score": avg(xs)}
            for (m, s), xs in by_model_survey.items()
        },
        "by_mode": {m: {"count": len(xs), "avg_score": avg(xs)} for m, xs in by_mode.items()},
        "by_model_mode": {
            f"{m}::{mode}": {"count": len(xs), "avg_score": avg(xs)}
            for (m, mode), xs in by_model_mode.items()
        },
        "by_survey_mode": {
            f"{s}::{mode}": {"count": len(xs), "avg_score": avg(xs)}
            for (s, mode), xs in by_survey_mode.items()
        },
    }


def summarize_conversations(convo_records: List[Dict]) -> Dict:
    by_model = defaultdict(list)
    by_survey = defaultdict(list)
    events_by_model = defaultdict(lambda: defaultdict(int))
    events_by_survey = defaultdict(lambda: defaultdict(int))
    events_total_by_model = defaultdict(int)
    turns_total_by_model = defaultdict(int)

    for item in convo_records:
        model = item.get("interviewer_model")
        survey = item.get("survey_name")
        used_turns = item.get("used_turns")
        event_counts = item.get("event_counts", {}) or {}
        event_total = item.get("event_total", 0) or 0
        if model is not None and isinstance(used_turns, int):
            by_model[model].append(used_turns)
            events_total_by_model[model] += int(event_total)
            turns_total_by_model[model] += int(used_turns)
            for k, v in event_counts.items():
                events_by_model[model][k] += int(v)
        if survey and isinstance(used_turns, int):
            by_survey[survey].append(used_turns)
            for k, v in event_counts.items():
                events_by_survey[survey][k] += int(v)

    def avg(xs: List[int]) -> float:
        return round(sum(xs) / len(xs), 2) if xs else 0.0

    return {
        "total_records": len(convo_records),
        "avg_turns_by_model": {m: avg(xs) for m, xs in by_model.items()},
        "avg_turns_by_survey": {s: avg(xs) for s, xs in by_survey.items()},
        "event_total_by_model": dict(events_total_by_model),
        "event_counts_by_model": {m: dict(v) for m, v in events_by_model.items()},
        "event_counts_by_survey": {s: dict(v) for s, v in events_by_survey.items()},
        "avg_events_by_model": {
            m: round(events_total_by_model[m] / len(by_model[m]), 2) if by_model[m] else 0.0
            for m in by_model
        },
        "event_rate_per_turn_by_model": {
            m: round(events_total_by_model[m] / turns_total_by_model[m], 4) if turns_total_by_model[m] else 0.0
            for m in turns_total_by_model
        },
    }


def main():
    score_path = os.path.join(OUTPUT_DIR, "score_result.jsonl")
    convo_path = os.path.join(OUTPUT_DIR, "conversation_result.jsonl")

    score_records = load_jsonl(score_path)
    convo_records = load_jsonl(convo_path)

    summary = {
        "score_summary": summarize_scores(score_records),
        "conversation_summary": summarize_conversations(convo_records),
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Saved summary to {SUMMARY_PATH}")
    # 控制台快速查看新增分组统计
    score_summary = summary.get("score_summary", {})
    print("by_mode:", score_summary.get("by_mode", {}))
    print("by_model_mode:", score_summary.get("by_model_mode", {}))


if __name__ == "__main__":
    main()
