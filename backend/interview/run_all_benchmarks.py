import json
import os
from pathlib import Path
from typing import Dict, List

from tqdm import tqdm

from config import project_model_config_candidates
from run_benchmark import BenchmarkRunner, load_config

BASE_DIR = Path(__file__).resolve().parent
BENCH_DIR = os.path.join(str(BASE_DIR), "benchmarks")
OUTPUT_DIR = os.path.join(str(BASE_DIR), "outputs")
SUMMARY_PATH = os.path.join(OUTPUT_DIR, "summary_scores.json")
FAILURE_PATH = os.path.join(OUTPUT_DIR, "run_failures.jsonl")


def resolve_runtime_config_path() -> str:
    candidates = project_model_config_candidates(BASE_DIR, "./project_config.json")
    for path in candidates:
        if path.exists():
            return str(path)
    return str(candidates[-1])


def parse_list_env(key: str, default: List[str]) -> List[str]:
    val = os.environ.get(key)
    if not val:
        return default
    return [x.strip() for x in val.split(",") if x.strip()]


def load_jsonl(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def list_benchmarks() -> List[str]:
    if not os.path.exists(BENCH_DIR):
        return []
    only_clean = os.environ.get("ONLY_CLEAN_BENCHMARKS", "true").strip().lower() in {"1", "true", "yes"}
    out: List[str] = []
    for name in os.listdir(BENCH_DIR):
        path = os.path.join(BENCH_DIR, name)
        if only_clean and not name.endswith("_clean"):
            continue
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "questionnaire.json")):
            out.append(path)
    return sorted(out)


def summarize_scores(score_records: List[Dict]) -> Dict:
    by_model: Dict[str, List[float]] = {}
    by_mode: Dict[str, List[float]] = {}
    for item in score_records:
        model = item.get("interviewer_model")
        score = (item.get("score") or {}).get("score")
        no_event = item.get("no_event_mode", False)
        ablation = item.get("ablation_mode", "direct")
        if model is None or score is None:
            continue
        score = float(score)
        by_model.setdefault(model, []).append(score)
        by_mode.setdefault(f"{ablation}::no_event={no_event}", []).append(score)

    def avg(xs: List[float]) -> float:
        return round(sum(xs) / len(xs), 4) if xs else 0.0

    return {
        "total_records": len(score_records),
        "by_model": {k: {"count": len(v), "avg_score": avg(v)} for k, v in by_model.items()},
        "by_mode": {k: {"count": len(v), "avg_score": avg(v)} for k, v in by_mode.items()},
    }


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    models = load_config(resolve_runtime_config_path())
    runner = BenchmarkRunner(models)

    interviewer_models = parse_list_env("INTERVIEWER_MODELS", ["qwen3-max", "deepseek-chat", "gpt-4o"])
    interviewee_model = os.environ.get("INTERVIEWEE_MODEL", "qwen3-max")
    handling_modes = parse_list_env("HANDLING_MODES", ["default"])
    # 默认不跑对比组；仅在显式传入环境变量时开启
    ablation_modes = parse_list_env("ABLATION_MODES", ["direct"])
    no_event_modes = [x.lower() == "true" for x in parse_list_env("NO_EVENT_MODES", ["true"])]
    event_trigger_prob = float(os.environ.get("EVENT_TRIGGER_PROB", "0.0"))
    free_chat_turn_limit = int(os.environ.get("FREE_CHAT_TURN_LIMIT", "2"))

    benches = list_benchmarks()
    total = len(benches) * len(interviewer_models) * len(handling_modes) * len(ablation_modes) * len(no_event_modes)
    with tqdm(total=total, desc="批量评测", ncols=90) as pbar:
        for bench_dir in benches:
            for model in interviewer_models:
                for handling_mode in handling_modes:
                    for ablation_mode in ablation_modes:
                        for no_event_mode in no_event_modes:
                            try:
                                runner.run_once(
                                    benchmark_dir=bench_dir,
                                    interviewer_model=model,
                                    interviewee_model=interviewee_model,
                                    output_dir=OUTPUT_DIR,
                                    handling_mode=handling_mode,
                                    ablation_mode=ablation_mode,
                                    no_event_mode=no_event_mode,
                                    event_trigger_prob=event_trigger_prob,
                                    free_chat_turn_limit=free_chat_turn_limit,
                                    compare_fill_modes=False,
                                )
                            except Exception as e:
                                with open(FAILURE_PATH, "a", encoding="utf-8") as f:
                                    f.write(json.dumps({
                                        "benchmark_dir": bench_dir,
                                        "interviewer_model": model,
                                        "interviewee_model": interviewee_model,
                                        "handling_mode": handling_mode,
                                        "ablation_mode": ablation_mode,
                                        "no_event_mode": no_event_mode,
                                        "error": str(e),
                                    }, ensure_ascii=False) + "\n")
                            pbar.update(1)

    scores = load_jsonl(os.path.join(OUTPUT_DIR, "score_result.jsonl"))
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summarize_scores(scores), f, ensure_ascii=False, indent=2)
    print(f"保存汇总: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
