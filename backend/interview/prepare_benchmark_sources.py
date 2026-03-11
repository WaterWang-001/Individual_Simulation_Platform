import json
import os
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_ROOT = os.path.join(BASE_DIR, "Benchmark", "数据", "dataset-1216")
TIME_MANAGEMENT_PATH = os.path.join(BASE_DIR, "Time_management_questionnaire.jsonl")
OUT_ROOT = os.path.join(BASE_DIR, "benchmark_sources")


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def strip_answers(questionnaire: Dict[str, Any]) -> Dict[str, Any]:
    out = json.loads(json.dumps(questionnaire, ensure_ascii=False))
    for q in out.get("questions", []):
        if "answer" in q:
            q.pop("answer")
    return out


def find_first_file(dir_path: str, names: List[str], suffixes: Optional[List[str]] = None) -> Optional[str]:
    if not os.path.isdir(dir_path):
        return None
    entries = os.listdir(dir_path)
    if suffixes:
        for f in entries:
            low = f.lower()
            if any(low.endswith(suf.lower()) for suf in suffixes):
                if any(token.lower() in low for token in names):
                    return os.path.join(dir_path, f)
        return None
    for f in entries:
        low = f.lower()
        if any(token.lower() in low for token in names):
            return os.path.join(dir_path, f)
    return None


def save_source_bundle(
    out_dir: str,
    dataset_name: str,
    questionnaire_template: Dict[str, Any],
    records: List[Dict[str, Any]],
    source_paths: Dict[str, str],
) -> None:
    ensure_dir(out_dir)
    with open(os.path.join(out_dir, "questionnaire_template.json"), "w", encoding="utf-8") as f:
        json.dump(questionnaire_template, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "records.jsonl"), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "dataset_name": dataset_name,
                "survey_name": questionnaire_template.get("survey_name"),
                "record_count": len(records),
                "source_paths": source_paths,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def prepare_dataset_1216() -> int:
    ensure_dir(OUT_ROOT)
    total = 0
    for dataset_name in sorted(os.listdir(DATASET_ROOT)):
        dataset_dir = os.path.join(DATASET_ROOT, dataset_name)
        if not os.path.isdir(dataset_dir):
            continue
        combined_path = find_first_file(dataset_dir, ["questionnaire_combined"], [".jsonl"])
        if not combined_path:
            continue
        template_path = find_first_file(dataset_dir, ["questionnaire", "questionaire"], [".json"])
        records_raw = load_jsonl(combined_path)
        records: List[Dict[str, Any]] = []
        for row in records_raw:
            q = row.get("questionnaire", {})
            respondent_id = str(row.get("id", len(records) + 1))
            records.append(
                {
                    "respondent_id": respondent_id,
                    "questionnaire_with_answers": q,
                }
            )
        if template_path and os.path.exists(template_path):
            questionnaire_template = load_json(template_path)
        elif records:
            questionnaire_template = strip_answers(records[0]["questionnaire_with_answers"])
        else:
            continue
        out_dir = os.path.join(OUT_ROOT, dataset_name)
        save_source_bundle(
            out_dir=out_dir,
            dataset_name=dataset_name,
            questionnaire_template=questionnaire_template,
            records=records,
            source_paths={
                "combined_path": combined_path,
                "template_path": template_path or "",
            },
        )
        total += 1
    return total


def prepare_time_management() -> None:
    if not os.path.exists(TIME_MANAGEMENT_PATH):
        return
    rows = load_jsonl(TIME_MANAGEMENT_PATH)
    records: List[Dict[str, Any]] = []
    for row in rows:
        q = row.get("questionnaire", {})
        records.append(
            {
                "respondent_id": str(row.get("id", len(records) + 1)),
                "questionnaire_with_answers": q,
            }
        )
    if not records:
        return
    template = strip_answers(records[0]["questionnaire_with_answers"])
    out_dir = os.path.join(OUT_ROOT, "international_students")
    save_source_bundle(
        out_dir=out_dir,
        dataset_name="international_students",
        questionnaire_template=template,
        records=records,
        source_paths={"combined_path": TIME_MANAGEMENT_PATH, "template_path": ""},
    )


def main() -> None:
    count = prepare_dataset_1216()
    prepare_time_management()
    print(f"Prepared dataset bundles: {count} + international_students")
    print(f"Output: {OUT_ROOT}")


if __name__ == "__main__":
    main()
